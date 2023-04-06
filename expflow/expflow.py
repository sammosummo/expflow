import datetime
import gzip
import re

from dataclasses import dataclass, field
from datetime import date, datetime as dt

"""Note about datetime.

I find this module super confusing. The module called datetime defines classes called
date and datetime, and the class datetime defines a method called date. Therefore, if
you do `import datetime` and then type `datetime.date`, you get the class date, which
is the correct one for typing dates. If you do `from datetime import datetime` and then
type `datetime.date`, you get the method, which isn't the correct one for typing dates.
My solution is to import the classes date and datetime from the module. Also note that
dataclasses-json doesn't support encoding or decoding of datetime.date into JSON, so
functions need to be defined explicitly for that purpose.

"""

from getpass import getuser
from logging import getLogger, Logger
from os import getcwd
from pathlib import Path
from socket import gethostname
from tempfile import TemporaryDirectory
from uuid import UUID, uuid4
from warnings import warn

from dataclasses_json import DataClassJsonMixin, config
from localnow import now
from logmixin import get_logger, LogMixin

module_logger: Logger = getLogger(__name__)
module_logger.debug(f"Importing {__name__} from {__file__}")
module_logger.debug(f"Creating a temporary directory for expflow data")
tmpdir: TemporaryDirectory = TemporaryDirectory()
module_logger.debug(f"Temporary directory created: {tmpdir.name}")
module_logger.debug(f"Setting expflow data directory to {tmpdir.name}")
expflow_dir: Path = Path(tmpdir.name)
module_logger.debug(f"Expflow data directory set to {expflow_dir}")
using_compression: bool = False
module_logger.debug(f"Initially setting using_compression flag to {using_compression}")
subdirs: list[str] = ["Participants", "Experiments", "Trials", "Trash", "Logs"]
module_logger.debug(f"Subdirectories: {subdirs}")
module_logger.debug(f"Defining statuses dictionary")
statuses: dict[str, dict[str, set[str] | str]] = {
    "pending": {
        "description": "Trial is scheduled to run later",
        "transitions": {"running", "skipped"},
    },
    "running": {
        "description": "Trial is running right now",
        "transitions": {"finished", "timed_out", "paused"},
    },
    "paused": {
        "description": "Trial is temporarily paused",
        "transitions": {"running"},
    },
    "timed_out": {
        "description": "Trial went on too long and has ended",
        "transitions": set(),
    },
    "finished": {
        "description": "Trial ended as expected",
        "transitions": set(),
    },
    "skipped": {
        "description": "Trial will not run",
        "transitions": set(),
    },
}
module_logger.debug(f"Defined statuses dictionary: {statuses}")
kw = {"repr": False, "compare": False, "hash": False, "init": True}
USER_DIR: Path = Path.home() / "Expflow"


def _get_subdir(subdir: str) -> Path:
    """Returns the path to a subdirectory of the expflow data directory.

    This function is used internally by expflow to get the path to a subdirectory of
    the expflow data directory. It is not intended to be used by users. The subdirectory
    is created if it does not already exist.

    Args:
        subdir: The name of the subdirectory to return.

    Returns:
        The path to the subdirectory.

    """
    logger: Logger = getLogger(f"{__name__}._get_subdir")
    logger.debug(f"Getting path to {subdir} subdirectory")
    if str(expflow_dir) == tmpdir.name:
        logger.warning("Using temporary directory; data will be lost when program ends")
        warn("Using temporary directory; data will be lost when program ends")
    path: Path = expflow_dir / subdir
    logger.debug(f"Path to {subdir} subdirectory is {path}")
    logger.debug(f"Creating {subdir} if subdirectory doesn't exist")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _get_pdir() -> Path:
    """Returns the path to the participant directory.

    This function is used internally by expflow to get the path to the participant
    directory. It is not intended to be used by users. The participant directory is
    created if it does not already exist.

    Returns:
        The path to the participant directory.

    """
    return _get_subdir("Participants")


def _get_edir() -> Path:
    """Returns the path to the experiment directory.

    This function is used internally by expflow to get the path to the experiment
    directory. It is not intended to be used by users. The experiment directory is
    created if it does not already exist.

    Returns:
        The path to the experiment directory.

    """
    return _get_subdir("Experiments")


def _get_tdir() -> Path:
    """Returns the path to the trial directory.

    This function is used internally by expflow to get the path to the trial directory.
    It is not intended to be used by users. The trial directory is created if it does
    not already exist.

    Returns:
        The path to the trial directory.

    """
    return _get_subdir("Trials")


def _get_trashdir() -> Path:
    """Returns the path to the trash directory.

    This function is used internally by expflow to get the path to the trash directory.
    It is not intended to be used by users. The trash directory is created if it does
    not already exist.

    Returns:
        The path to the trash directory.

    """
    return _get_subdir("Trash")


def _get_ldir() -> Path:
    """Returns the path to the logs directory.

    This function is used internally by expflow to get the path to the logs directory.
    It is not intended to be used by users. The logs directory is created if it does
    not already exist.

    Returns:
        The path to the logs directory.

    """
    return _get_subdir("Logs")


def set_expflow_dir(path: str | Path) -> None:
    """Sets the expflow data directory.

    Users should call this function at the beginning of their program. If this function
    is not called, expflow will use a temporary directory that will be deleted when the
    program ends and issue numerous annoying warnings about it. This function will also
    create several subdirectories if they do not already exist.

    Args:
        path: The path to the expflow data directory.

    """
    global expflow_dir
    if path is None:
        path = getcwd()
    expflow_dir = Path(path)
    [_get_subdir(p).mkdir(parents=True, exist_ok=True) for p in subdirs]


def get_expflow_dir() -> Path:
    """Returns the path to the expflow data directory.

    Returns:
        The path to the expflow data directory.

    """
    if expflow_dir == Path(tmpdir.name):
        logger: Logger = getLogger(f"{__name__}.{get_expflow_dir.__name__}")
        logger.warning("Using temporary directory; data will be lost when program ends")
        warn("Using temporary directory; data will be lost when program ends")
    return expflow_dir


def is_valid_id(id_: str) -> bool:
    """Checks if a string is a valid expflow ID.

    Args:
        id_: The string to check.

    Returns:
        True if the string is a valid expflow ID, False otherwise.

    """
    get_logger().debug(
        f"Checking if {id_} is a valid ID (must be at least 4 characters "
        f"long and contain only letters, numbers, underscores, and "
        f"dashes)"
    )
    return len(id_) >= 3 and bool(re.match(r"^[a-zA-Z0-9_\-]+$", id_))


def _pe(p: Path | None) -> str | None:
    """Private function for encoding strings as Path objects.

    Args:
        p: Path to encode

    Returns:
        String representation of the path or None.

    """
    if isinstance(p, Path):
        return str(p)


def _pd(s: str | None) -> Path | None:
    """Private function for decoding strings as Path objects.

    Args:
        s: String to decode.

    Returns:
        Path object or None if `s` does not contain ".json".

    """
    if isinstance(s, str) and ".json" in s:
        return Path(s)


@dataclass
class _IdentificationMixin(LogMixin):
    """Mixin dataclass to add identification information to participants, experiments, or
    trials.

    "Identification information" is information that can be used to identify the object
    in question. This includes the hostname and username of the computer on which the
    object was created, a UUID, the date and time at which the object was created, the
    name of the class from which the object was created, and the name of the base class
    from which the object was created.

    On initialisation, classes that inherit from this mixin will make sure that the
    `class_name` field is set to the name of the class from which the object was created,
    and the `base_name` field is "Participant", "Experiment", or "Trial" depending on
    which of these was subclassed. This is moot if the class was created without setting
    these fields, but a useful validation check if the class was created by loading a
    JSON file.


    Fields:
        hostname: The hostname of the computer.
        username: The username of the user.
        uuid: The UUID of the object.

    """

    hostname: str = field(default_factory=gethostname, **kw)
    username: str = field(default_factory=getuser, **kw)
    datetime_created: dt = field(default_factory=now, **kw)
    uuid: UUID = field(default_factory=uuid4, **kw)
    class_name: str | None = field(default=None, **kw)
    base_name: str | None = field(default=None, **kw)

    def __post_init__(self) -> None:
        """Sets the class and base names immediately after initialisation if not already
        set."""
        if self.class_name is None:
            self.class_name = self._get_class_name()
        if self.base_name is None:
            self.base_name = self._get_base_name()
        self._validate()

    def _get_class_name(self) -> str:
        """Returns the name of the class from which the object was created."""
        self.get_logger().debug(f"Getting class name for {self}")
        return self.__class__.__name__

    def _get_base_name(self) -> str:
        """Returns the name of the base class from which the object was created."""
        self.get_logger().debug(f"Getting base name for {self}")
        if self.class_name in ("Participant", "Experiment", "Trial"):
            return self.class_name
        for base in self.__class__.__bases__:
            if base.__name__ in ("Participant", "Experiment", "Trial"):
                return base.__name__

    def _validate(self) -> None:
        """Raises an exception if the class definition is invalid for some reason."""
        logger: Logger = self.get_logger()
        m = "Probably loaded information using the wrong class method."
        a = self._get_class_name()
        b = self.class_name
        if a != b:
            msg: str = f"Class name mismatch: {a} != {b}. {m}"
            logger.error(msg)
            raise WrongClassError(msg)
        a = self._get_base_name()
        b = self.base_name
        if a != b:
            msg: str = f"Base name mismatch: {a} != {b}. {m}"
            logger.error(msg)
            raise WrongClassError(msg)

    @property
    def is_participant(self) -> bool:
        """Returns True if the object is a participant."""
        return self.base_name == "Participant"

    @property
    def is_experiment(self) -> bool:
        """Returns True if the object is an experiment."""
        return self.base_name == "Experiment"

    @property
    def is_trial(self) -> bool:
        """Returns True if the object is a trial."""
        return self.base_name == "Trial"


@dataclass
class _SerialisationMixin(_IdentificationMixin, DataClassJsonMixin):
    """Mixin dataclass to add serialisation to participants, experiments, or trials.

    Fields:
        path: The default path to the JSON representation of the object.
        datetime_last_saved: The datetime when the object was last saved.
        compression: Whether to use compression when saving the object.

    Class methods:
        load: Loads the object from a JSON file.
        from_json: Returns an object from its JSON representation.

    Instance methods:
        save: Saves the object to a JSON file.
        to_json: Returns the JSON representation of the object.

    """

    path: Path | None = field(
        metadata=config(encoder=_pe, decoder=_pd),
        default=None,
        **kw,
    )
    datetime_last_saved: dt | None = field(default=None, **kw)
    compression: bool = field(default_factory=lambda: using_compression, **kw)

    def __post_init__(self) -> None:
        """Performs numerous validation checks to ensure the object was created or loaded
        properly."""
        super().__post_init__()
        self.no_save_on_gc: bool = False
        self.path: Path = self._get_default_path()
        if self.datetime_last_saved is None:
            self._ensure_default_path_doesnt_exist()
            self.save()

    def _get_default_path(self) -> Path | None:
        """Returns the default path of the object."""
        logger: Logger = self.get_logger()
        logger.debug("Getting default path")
        if not hasattr(self, "participant_id") or self.participant_id is None:
            logger.warning("Participant ID not found, cannot return default path")
            return
        suffix = ".json" + (".gz" if self.compression else "")
        if self.is_participant:
            return _get_pdir() / (self.participant_id + suffix)
        elif self.is_experiment:
            if not hasattr(self, "experiment_id") or self.experiment_id is None:
                logger.warning("Experiment ID not found, cannot return default path")
                return
            f = ".".join([self.participant_id, self.experiment_id]) + suffix
            return _get_edir() / f
        else:
            msg: str = "Cannot get default path for trial"
            logger.error(msg)
            raise ValueError(msg)

    @classmethod
    def get_base_name(cls) -> str:
        """Returns the name of the base class from which the object was created."""
        cls.get_logger().debug(f"Getting base name for {cls}")
        if cls.__name__ in ("Participant", "Experiment", "Trial"):
            return cls.__name__
        for base in cls.__bases__:
            if base.__name__ in ("Participant", "Experiment", "Trial"):
                return base.__name__

    @classmethod
    def get_default_path(
        cls,
        participant_id: str,
        experiment_id: str | None = None,
        compression: bool = using_compression,
    ) -> Path:
        """Returns the default path of the object."""
        logger: Logger = cls.get_logger()
        logger.debug("Getting default path")
        suffix = ".json" + (".gz" if compression else "")
        if cls.get_base_name() == "Participant":
            return _get_pdir() / (participant_id + suffix)
        elif cls.get_base_name() == "Experiment":
            if experiment_id is None:
                logger.warning("Experiment ID not found, cannot return default path")
                return
            f = ".".join([participant_id, experiment_id]) + suffix
            return _get_edir() / f
        else:
            msg: str = "Cannot get default path for trial"
            logger.error(msg)
            raise ValueError(msg)

    def _ensure_default_path_doesnt_exist(self) -> None:
        """Raises an exception if the default path already exists."""
        logger: Logger = self.get_logger()
        logger.debug("No datetime_last_saved; should be a fresh object")
        path = self._get_default_path()
        logger.debug("Ensuring default path doesn't already exist")
        if path is None:
            logger.warning("Path is None, cannot ensure path doesn't already exist")
            return
        if path.exists() or (Path(str(path) + ".gz")).exists():
            msg: str = f"{self.path} or {Path(str(path) + '.gz')} already exists"
            logger.error(msg)
            if self.base_name == "Participant":
                msg += " (participant previously created)"
                raise ParticipantExistsError(msg)
            elif self.base_name == "Experiment":
                msg += " (participant already started experiment)"
                raise ExperimentExistsError(msg)
            else:
                raise FileExistsError(msg)

    def save(self) -> None:
        """Save the data to a JSON file at the default path.

        This is the preferred way to save data.

        """
        logger: Logger = self.get_logger()
        logger.info(f"Saving {self} to {self.path}")
        self.datetime_last_saved = now()
        if self.path is None:
            msg = "Path is None, cannot save"
            logger.warning(msg)
            return
        if str(expflow_dir) == tmpdir.name:
            msg: str = "Using temporary directory; data will be lost when program ends"
            logger.warning(msg)
            warn(msg)
        self.to_json(self.path)
        logger.info(f"Saved {self} to {self.path}")

    def to_json(self, path: Path | str | None = None, **kwargs) -> None | str:
        """Write to JSON format.

        The preferred way to save data is to use the `save` method, which updates the
        `datetime_last_saved` field and saves to the default path. However, this method
        can be used to save to a custom path or to return the JSON string without saving
        to a file, which can be useful for debugging or data analysis.

        Args:
            path: file path or None. If None, the JSON string is returned. If a file path
                is given, the JSON string is written to the file.

        Returns:
            The JSON string or None.
            **kwargs: Keyword arguments to pass to `json.dumps`.

        """
        msg: str = "Using temporary directory; data will be lost when program ends"
        logger: Logger = self.get_logger()
        if not self.compression:
            j: str = super().to_json(indent=2, **kwargs)
        else:
            j: str = super().to_json(**kwargs)
        if path is not None:
            if str(expflow_dir) == tmpdir.name:
                logger.warning(msg)
                warn(msg)
            if not self.compression:
                with open(path, "w") as fp:
                    fp.write(j)
            else:
                with gzip.open(path, "wt") as fp:
                    fp.write(j)
        else:
            logger.info(f"Returning {self} JSON string")
            return j

    @classmethod
    def load(
        cls,
        participant_id: str,
        experiment_id: str | None = None,
    ) -> "_SerialisationMixin":
        """Load an instance of this dataclass from a JSON file at the default path.

        Args:
            path = str | Path: The path to the JSON file. If no path is given,
                the default path is used.

        Returns:
            The object.

        """
        logger: Logger = cls.get_logger()
        path = cls.get_default_path(participant_id, experiment_id, False)
        if not path.exists():
            msg: str = f"{path} does not exist, trying {path}.gz"
            logger.debug(msg)
            path = cls.get_default_path(participant_id, experiment_id, True)
            if not path.exists():
                msg: str = f"{path} does not exist either"
                logger.error(msg)
                raise FileNotFoundError(msg)
        if path is not None:
            if str(path).endswith(".gz"):
                with gzip.open(path, "rt") as fp:
                    return cls.from_json(fp.read())
            else:
                with open(path, "r") as fp:
                    return cls.from_json(fp.read())
        else:
            cls.get_logger().warning("Cannot save if without a default path")

    def delete(self) -> None:
        """Delete the file at the default path."""
        logger: Logger = self.get_logger()
        if self.path is None:
            logger.warning("Cannot delete if without a default path")
            return
        if self.path.exists():
            self.path.unlink()
            logger.info(f"Deleted {self.path}")
        else:
            logger.warning(f"{self.path} does not exist")
        logger.debug("Since we deleted the file, we should turn off saving during g.c.")
        if self.no_save_on_gc is False:
            self.no_save_on_gc = True

    def __del__(self):
        logger: Logger = self.get_logger()
        logger.info(f"Garbage collecting {self}")
        try:
            if self.path is not None and self.path.exists():
                logger.debug(f"Path is {self.path} and exists")
                if not self.no_save_on_gc:
                    logger.debug(f"Saving {self} before garbage collection")
                    self.save()
                else:
                    logger.debug(f"Not saving {self} before g.c.")
        except ImportError:
            logger.error("Got an ImportError, probably because we're in a test")
            pass


@dataclass
class _ParReqFieldsMixin:
    """Participant required fields mixin dataclass.

    This is a private class and should not be called directly. Due to the funky way
    dataclasses handle field definitions, it is necessary to create an intermediate
    dataclass containing required fields and put it at the end of the inheritence
    sequence.
    """

    participant_id: str


@dataclass
class Participant(_SerialisationMixin, _ParReqFieldsMixin):
    """Participant dataclass.

    This is the dataclass for participants. Users should create an instance of this class
    (or one of its subclasses) for each participant in an experiment prior to creating
    the experiment instance.

    Participant objects have one required field called `participant_id`, which must be
    unique for each participant. Users are forced to specify this field when creating a
    participant object, and an error is raised if the ID already belongs to someone else
    (i.e., there is already a participant file with the same ID in the participant
    directory).

    There are two reasons to re-use a participant ID: (1) the same participant is about
    to start a second experiment or resume a paused experiment; and (2) the participant
    ID was used previously in error. If (1), the user must load the previously saved
    participant object rather than create a new object. If (2), the erroneous saved file
    should be deleted. Please note that under no circumstances can a participant repeat
    an experiment they previously completed.

    There are several optional fields that can be added to the participant dataclass:

        dob: Date of birth. Should be a `date` object.
        age: Age. Should be an `int` or `float`. Doesn't make sense to use this if `dob`
            is specified.
        gender: Participant gender.
        language: Participant language. Should be a language and region code.
        comments: Any comments about the participant.
        group: Participant group.

    These do not appear in the repr or str methods, but they are saved to the JSON file.
    If you want to add additional fields, you can do so by creating a subclass:

    ```python
    @dataclass
    class MyParticipant(Participant):
        my_field: int: 0
    ```

    Unfortunately, you have to specify default values for the new fields, even if you
    want them to be required. You can define required fields, but it is a bit cumbersome
    (sorry). You either need to overload the `__post_init__()` method to perform a check
    that the required field doesn't match the default value or use a mixin. There are
    examples in the code base. Personally, I would just live with using default values.

    Participant objects check all that participant IDs are unique in all subclasses. This
    means that you can't have `Participant(participant_id="test")` and
    `SomeSubclassParticipant(participant_id="test")`. This is a good thing!

    Participant objects have `save()`, `load()`, `to_json()` and `from_json()`methods for
    serialisation.

    """

    dob: date | None = field(default=None, **kw, metadata=config(
            encoder=lambda x: date.isoformat(x) if x is not None else None,
            decoder=lambda x: date.fromisoformat(x) if x is not None else None,
    ))  # not `datetime.date` ... see note!
    age: float | int | None = field(default=None, **kw)
    gender: str | None = field(default=None, **kw)
    language: str | None = field(default=None, **kw)
    comments: str | None = field(default=None, **kw)
    group: str | None = field(default=None, **kw)
    temporary_participant: bool = field(default=False, **kw)

    def __post_init__(self):
        super().__post_init__()
        if not is_valid_id(self.participant_id):
            msg: str = f"Invalid participant ID: {self.participant_id}"
            self.get_logger().error(msg)
            raise ValueError(msg)


@dataclass
class _ExampleParticipantReqFields:
    example_field: str


@dataclass
class ExampleSubclassParticipant(Participant, _ExampleParticipantReqFields):
    """This is an example of how to add required fields to a subclass of Participant."""


@dataclass
class AnotherExampleSubclassParticipant(Participant):
    """This is an example of how to add required fields to a subclass of Participant."""

    example_field: str = ""

    def __post_init__(self):
        super().__post_init__()
        assert self.example_field != "", "Missing required field"


@dataclass
class _StatusMixin(LogMixin):
    """Status mixin dataclass.

    This class is not meant to be instantiated directly. Instead, it is subclassed by
    the Experiment and Trial classes (and their subclasses), adding status functionality.
    `status` is a special property that can only be one of a few values and can be
    changed from one value to another only in certain ways. The `status` setter performs
    these checks and other actions, such as updating the `status_history` list. The value
    of `status` is mirrored in the `current_status` field.

    Fields:
        current_status: What is the current status of the experiment or trial?
        status_history: A list of dictionaries containing the status and the datetime
            at which the status was set.
        event_history: A blank list for users to add events to.
        datetime_started: When did the experiment or trial start?
        datetime_finished: When did the experiment or trial finish?
        datetimes_paused: A list of tuples containing the start and end datetimes of
            each pause.
        datetime_last_paused: When was the experiment or trial last paused?
        duration: How long did the experiment or trial last?

    Properties:
        status: The current status of the experiment or trial.
        is_pending: Is the experiment or trial pending?
        is_running: Is the experiment or trial running?
        is_paused: Is the experiment or trial paused?
        is_finished: Is the experiment or trial finished?
        is_timed_out: Has the experiment or trial timed out?
        is_skipped: Has the experiment or trial been skipped?

    Methods:
        set_status: Set the current status of the experiment or trial.
        run: Set the status to "running".
        resume: Alias for run.
        start: Alias for run.
        unpause: Alias for run.
        pause: Set the status to "paused".
        finish: Set the status to "finished".
        finish_normally: Alias for finish.
        skip: Set the status to "skipped".
        time_out: Set the status to "timed_out".
        time_out: Alias for time out.
        get_duration: Get the duration of the experiment or trial.

    """

    current_status: str = field(default="pending", **kw)
    status_history: list[dict[str, str | dt]] = field(default_factory=list, **kw)
    event_history: list[dict[str, str | dt]] = field(default_factory=list, **kw)
    datetime_started: dt | None = field(default=None, **kw)
    datetime_finished: dt | None = field(default=None, **kw)
    datetimes_paused: list[tuple[dt, dt]] = field(default_factory=list, **kw)
    datetime_last_paused: dt | None = field(default=None, **kw)
    duration: float | None = field(default=None, **kw)

    @property
    def is_pending(self) -> bool:
        return self.current_status == "pending"

    @property
    def is_running(self) -> bool:
        return self.current_status == "running"

    def run(self) -> None:
        self.set_status("running")

    def start(self) -> None:
        self.run()

    def resume(self) -> None:
        self.run()

    def unpause(self) -> None:
        self.run()

    @property
    def is_paused(self) -> bool:
        return self.current_status == "paused"

    def pause(self) -> None:
        self.set_status("paused")

    @property
    def is_finished(self) -> bool:
        return self.current_status == "finished"

    def finish(self) -> None:
        self.set_status("finished")

    def finish_normally(self) -> None:
        self.finish()

    @property
    def is_timed_out(self) -> bool:
        return self.current_status == "timed_out"

    def time_out(self) -> None:
        self.set_status("timed_out")

    @property
    def is_skipped(self) -> bool:
        return self.current_status == "skipped"

    def skip(self) -> None:
        self.set_status("skipped")

    @property
    def status(self) -> str:
        return self.current_status

    def set_status(self, s) -> None:
        self.status = s

    @status.setter
    def status(self, new_status) -> None:
        """Set the `current_status` field and update other fields as necessary."""
        then: dt = now()
        logger: Logger = self.get_logger()
        old_status: str = self.current_status[:]  # to avoid any monkey business
        logger.debug(f"Changing status of {self} from {old_status} to {new_status}")

        if new_status not in statuses:
            m: str = f"{new_status} is not an acceptable status."
            logger.error(m)
            raise ValueError(m)

        if new_status not in statuses[old_status]["transitions"]:
            m: str = f"Cannot switch from {old_status} to {new_status}."
            logger.error(m)
            raise ValueError(m)

        logger.debug("Recording status change in status_history")
        dic: dict[str, str | dt] = {
            "old_status": old_status,
            "new_status": new_status,
            "datetime": then,
        }
        self.status_history.append(dic)

        self.current_status = new_status
        logger.debug(f"Changed status of {self} from {old_status} to {new_status}")

        logger.debug("Updating datetime fields as necessary")
        if new_status == "running":
            if old_status == "paused":
                logger.debug("Updating datetimes_paused")
                pause = (self.datetime_last_paused, then)
                self.datetimes_paused.append(pause)
            elif old_status == "pending":
                logger.debug("Updating datetime_started")
                self.datetime_started = then
        elif new_status == "finished" or new_status == "timed_out":
            logger.debug("Updating datetime_finished")
            self.datetime_finished = then
            self.duration = self.get_duration()
        elif new_status == "paused":
            logger.debug("Updating datetime_last_pause")
            self.datetime_last_paused = then

    def get_duration(self) -> float | None:
        """Return the duration in seconds.

        If not finished, returns None. If finished, returns datetime_finished minus
        datetime_started, minus the sum of the durations of all pauses.

        """
        self.get_logger().debug("Calculating duration")
        if self.datetime_finished is None:
            self.get_logger().warning("Cannot calculate duration if not finished")
            return None
        dur = (self.datetime_finished - self.datetime_started).total_seconds()
        for start, end in self.datetimes_paused:
            dur -= (end - start).total_seconds()
        return dur


@dataclass
class Trial(_IdentificationMixin, _StatusMixin, LogMixin, DataClassJsonMixin):
    """Trial dataclass.

    This is the base dataclass for trials. Users should create an instance of this class
    (or one of its subclasses) for each trial in an experiment.

    Trial dataclasses have several optional user-specifiable fields:
        stimulus: Information presented to the participant.
        response: The participant's subsequent behavior.
        trial_number: The trial number within the experiment.
        block_number: The block number within the experiment.
        condition: The condition of the trial.
        practice: Whether the trial is a practice trial.

    These can be set during or after instantiation. It makes sense to set `stimulus`
    before the trial is run and `response` afterwards, but you can do whatever you want.

    Trials also contain several automatically managed fields that should not be changed
    by the user. The most important one is `current_status`, which keeps track of the
    trial's progress in the context of the experiment. Expflow performs several checks
    whenever this field is changed to ensure that the trial is being used correctly.
    There is also a `status_history` field that records the history of changes to the
    `current_status` field.

    Another useful automatically managed field is `duration`, which is the total time
    taken to complete the trial. This is calculated automatically when the trial is
    marked as finished.

    The `event_history` field is meant to be set by the user to record any events that
    occur during the trial but aren't captured elsewhere.

    """

    stimulus: str | list | float | int | dict | set | None = None
    response: str | list | float | int | dict | set | None = None
    trial_number: int | None = None
    block_number: int | None = None
    condition: str | None = None
    practice: bool = False


@dataclass
class _ExpReqFieldsMixin:
    participant_id: str
    experiment_id: str


def _flexible_trial_dec(lst: list) -> list[Trial]:
    """Private function to create a Trial subclass from a list of dicts.

    Without this function, trial decoding will fail if the decoded object is a subclass
    of Trial. This function allows subclasses to be decoded correctly. It's a bit hacky,
    as the function uses the `globals()` function to access the global namespace and find
    the class that corresponds to the `class_name` field in the dict. If the class was
    defined in a different module, this function will fail

    """
    x = []
    for dic in lst:
        y = globals()[dic["class_name"]].from_dict(dic)
        x.append(y)
    return x


@dataclass
class Experiment(_SerialisationMixin, _StatusMixin, _ExpReqFieldsMixin):
    """Experiment dataclass.

    This is the dataclass for experiments. Users should create an instance of this class
    (or one of its subclasses) each time a new participant is about to run an experiment,
    ideally after creating the corresponding participant object.

    Experiment objects have two user-specifiable fields: `participant_id` and
    `experiment_id`. The combination of these IDs must be unique. In other words, a
    single participant can perform multiple different experiments, and multiple
    participants can perform the same experiment, but the same participant cannot perform
    the same experiment more than once (this is the "golden rule" of expflow).

    Users are forced to specify both fields when creating an experiment object, and an
    error is raised if the combination already exists (i.e., there is already an
    experiment file with the same ID combination in the experiment directory).

    There are two reasons to re-use an ID combination: (1) a participant is about to
    resume a paused experiment; and (2) a participant or experiment ID was used
    previously in error. If (1), the user must load the previously saved experiment
    object rather than create a new object. If (2), the erroneous saved file should be
    deleted. Again, under no circumstances can a participant repeat an experiment they
    previously completed.

    If you want to add additional fields to the experiment dataclass, you can do so
    by subclassing this class and adding the additional fields. However, I don't think it
    makes sense to do this, since it is usually the participant and/or trials where
    extra specific information is desirable. On the other hand, users may want to
    subclass the experiment dataclass to modify the experimental logic, but this is not
    covered here.

    Like participant objects, experiment objects have serialisation methods. They also
    have several extra automatically managed fields. The most important one is
    `current_status`, which keeps track of the trial's progress in the context of the
    experiment. Expflow performs several checks whenever this field is changed to ensure
    that the experiment object is being used correctly. There is also a `status_history`
    field that records the history of changes to the `current_status` field.

    Another useful automatically managed field is `duration`, which is the total time
    taken to complete the experiment. This is calculated automatically when the
    experiment is marked as finished.

    The `event_history` field is meant to be set by the user to record any events that
    occur during the trial but aren't captured elsewhere.

    """

    trial_index: int | None = field(default=None, **kw)
    trials: list[Trial] = field(default_factory=list, **kw)

    def __post_init__(self):
        super().__post_init__()
        self._check_participant_exists()
        self._check_experiment_wasnt_interrupted()
        if not is_valid_id(self.participant_id):
            msg: str = f"Invalid participant ID: {self.participant_id}"
            self.get_logger().error(msg)
            raise ValueError(msg)
        if not is_valid_id(self.experiment_id):
            msg: str = f"Invalid experiment ID: {self.experiment_id}"
            self.get_logger().error(msg)
            raise ValueError(msg)

    def _check_participant_exists(self):
        logger: Logger = self.get_logger()
        p1 = Participant.get_default_path(self.participant_id, compression=False)
        p2 = Participant.get_default_path(self.participant_id, compression=True)
        logger.debug(f"Checking if participant exists: {p1} or {p2}")
        if not p1.exists() and not p2.exists():
            m: str = "Participant does not exist, create a participant object first"
            logger.error(m)
            logger.debug("Removing experiment file")
            self.path.unlink()
            raise ParticipantDoesNotExistError(m)

    def _check_experiment_wasnt_interrupted(self):
        logger: Logger = self.get_logger()
        if self.is_running:
            msg: str = (
                "Experiment was loaded while it was running, which should not "
                "happen. Pausing experiment now. Please note that the timings for the "
                "experiment will be incorrect."
            )
            logger.warning(msg)
            warn(msg)
            self.pause()

    @property
    def current_trial(self) -> Trial | None:
        return self.trials[self.trial_index]

    @property
    def previous_trial(self) -> Trial:
        return self.trials[self.trial_index - 1]

    @property
    def next_trial(self) -> Trial:
        return self.trials[self.trial_index + 1]

    @property
    def remaining_trials(self) -> list[Trial]:
        return self.trials[self.trial_index + 1 :]

    @property
    def is_first_trial(self) -> bool:
        return self.trial_index == 0

    def __del__(self):
        self.get_logger().debug("Deleting experiment object")
        if self.is_running:
            self.get_logger().debug("Experiment was running, so it is now paused")
            self.pause()
            self.current_trial.pause()
        super().__del__()

    def __len__(self):
        return len(self.trials)

    def __iter__(self):
        return self

    def __next__(self):
        logger: Logger = self.get_logger()
        logger.debug(f"Iterating the experiment. Trial index is {self.trial_index}")

        if self.is_pending or self.is_paused:
            logger.debug("Experiment is pending or paused, so it is now running")
            self.run()

        if self.trial_index is None:
            logger.debug("Trial index is None, starting the experiment")
            self.trial_index = 0
        else:
            logger.debug("Trial index is a number, moving to the next trial")
            self.trial_index += 1

        if self.trial_index > 0:
            logger.debug("Updating statuses of previous trial if necessary")
            if self.previous_trial.is_running:
                logger.debug("Previous trial was running, so it is now finished")
                self.previous_trial.finish()

        logger.debug(f"Updating statuses of current trial if necessary")
        try:
            if self.current_trial.is_pending:
                logger.debug("Current trial was pending, so it is now running")
                self.current_trial.run()
            elif self.current_trial.is_paused:
                logger.debug("Current trial was paused, so it is now running")
                self.current_trial.unpause()
            elif self.current_trial.is_skipped:
                logger.debug("Current trial was skipped, iterating again")
                next(self)
        except IndexError:
            logger.debug("There is no current trial, so nothing to update")

        self.save()

        if self.trial_index >= len(self.trials):
            logger.debug("Experiment finished")
            self.finish()
            self.trial_index = None
            raise StopIteration

        return self.current_trial

    def _ok_to_add_trial(self) -> None:
        """Check if it is OK to add a trial to the experiment."""
        if self.is_finished or self.is_skipped or self.is_timed_out:
            msg: str = "Can't add trial to finished, skipped, or timed out experiment"
            self.get_logger().error(msg)
            raise ValueError(msg)

    def _is_trial(self, trial) -> None:
        """Check if the object is a trial."""
        if not isinstance(trial, Trial):
            msg: str = "Can only append trials to experiments"
            self.get_logger().error(msg)
            raise ValueError(msg)

    def append_trial(self, trial: Trial):
        """Append a trial to the experiment."""
        self._ok_to_add_trial()
        self._is_trial(trial)
        self.trials.append(trial)
        self.save()

    def append_trials(self, trials: list[Trial]):
        """Append multiple trials to the experiment."""
        for trial in trials:
            self.append_trial(trial)

    def insert_trial(self, trial: Trial, index: int):
        """Insert a trial into the experiment."""
        self._ok_to_add_trial()
        self._is_trial(trial)
        self.trials.insert(index, trial)
        self.save()

    def pause(self) -> None:
        super().pause()
        if self.trial_index is not None:
            self.current_trial.pause()
        self.save()

    def skip(self) -> None:
        super().skip()
        if self.trial_index is not None:
            self.current_trial.skip()
            [trial.skip() for trial in self.remaining_trials]
        self.save()

    def time_out(self) -> None:
        super().time_out()
        if self.trial_index is not None:
            self.current_trial.time_out()
            [trial.skip() for trial in self.remaining_trials]
        self.save()


class ParticipantExistsError(FileExistsError):
    pass


class ExperimentExistsError(FileExistsError):
    pass


class WrongClassError(TypeError):
    pass


class ParticipantDoesNotExistError(FileNotFoundError):
    pass


def get_participant_ids() -> list[str]:
    """Get a list of participant IDs."""

    return [f.stem.replace(".json", "") for f in _get_pdir().glob("*.json*")]


def get_experiment_ids() -> list[str]:
    """Get a list of experiment IDs."""
    return list(
        {f.stem.replace(".json", "").split(".")[1] for f in _get_edir().glob("*.json*")}
    )


def get_participated_in(participant_id: str) -> list[str]:
    """Get a list of experiment IDs that a participant has participated in."""
    return list(
        {
            f.stem.replace(".json", "").split(".")[1]
            for f in _get_edir().glob(f"{participant_id}.*.json*")
        }
    )