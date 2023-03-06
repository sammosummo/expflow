# Expflow
  
## Description  
  
Expflow is a Python library that controls the flow and handles the data of psychological experiments. While it isn't a 
full-fledged experiment builder like [PsychoPy](https://www.psychopy.org), it may be used with other tools to create 
robust experiments with minimal coding.
  
## Installation  
  
Expflow is available on PyPI and can be installed in the typical way with `pip`:  
  
```bash  
pip install expflow
```  
  
## Tutorial  
  
### Overview  

Expflow has strong opinions about how psychological experiments should be structered and coded, and performs extensive 
automatic bookkeeping and numerous validation checks under the hood to ensure that the user's code is consistent with 
these opinions.

Expflow defines an experiment as a sequence of trials presented to a participant. Typically, trials are identical except
for a small number of critical details, such as the stimulus. The participant makes a response on each trial, after 
which the trial ends. The next trial begins after the previous one. After the last trial, the experiment is finished.

### Logging  
  
Expflow makes extensive use of the [logging](https://docs.python.org/3/library/logging.html) module. The first few times
you use expflow, I recommend setting up basic logging at the most verbose level at beginning of your experiment script, 
which will allow you to see exactly what expflow does. If blazing fast performance is not a major concern — which 
typically it isn't, because psychological experiment are often simple things and modern computers are powerful — you 
could leave verbose logging switched on all the time (that's what I do). 
  
```python  
import logging  
  
logging.basicConfig(level=logging.DEBUG)  
logging.debug("Hello, world!")  
```  

The rest of this tutorial will now print many log message to the console.

### Importing expflow

Import expflow as follows.
  
```python  
import expflow  
```  
  
### Directories

#### Temporary directory
  
See the bit about creating a temporary directory in the log output?

Expflow needs somewhere to store data right away, and the default behaviour is to use a temporary directory. This is 
suitable for testing, but a bad idea for real work, because the data you generate will be lost when the program ends. 
Expflow will bug you with warnings if you don't set a permanent data directory. For example, try this:

```python
expflow.get_expflow_dir()  # produces a warning
```

#### Permanent directory

To set a permanent directory, use the `set_expflow_dir` function. You can pass any valid writable path to a directory. A
good choice is a dedicated subdirectory of your home directory. For convenience, expflow provides this as a constant 
called `expflow.USER_DIR`. 
  
```python  
expflow.set_expflow_dir(expflow.USER_DIR)  # set a dir
expflow.get_expflow_dir()  # prints something like `/Users/username/Expflow`
```  

#### Subdirectories

The function `set_expflow_dir` creates several subdirectories if they don't already exist. These are used to store 
different types of data. Currently, participant data are stored in the `participants` subdirectory and experiment data 
are stored in the `experiment` subdirectory. The others will be used by future versions of expflow.

### Cleaning up
  
Before we go on, let's take a moment delete some files that may exist in your user directory if you ran this tutorial
previously. 
  
```python  
for i in range(1, 10):  
    (expflow.USER_DIR / "Participants" / f"example_p{i}.json").unlink(True)  
    (expflow.USER_DIR / "Experiments" / f"example_p{i}.example_e1.json").unlink(True) 
```  
  
### Participants 

#### Creating participants
  
A participant is a person who takes part in an experiment. In expflow, a participant is represented by a `Participant` 
object. You should create an instance of this class for each participant in an experiment.

```python  
p = expflow.Participant("example_p1")  # creates a new participant
```

Participant objects are [dataclasses](https://docs.python.org/3/library/dataclasses.html). The single required argument
becomes a field called `participant_id`, which must be a unique string for each participant. Other optional fields you 
can set are:

- `dob`: Date of birth. Should be a `date` object.
- `age`: Age. Should be an `int` or `float`. Doesn't make sense to use this if `dob` is specified.
- `gender`: Participant gender.
- `language`: Participant language.
-  `comments`: Any comments about the participant.
-  `group`: Participant group.

There are other fields as well. You can see them all like so:
  
```python  
import dataclasses  
  
for field in dataclasses.fields(p):  
    logging.info(f"{field.name}: {getattr(p, field.name)}")  
```  

However, **don't go changing the values of the other fields willy-nilly!** Expflow manages them  
automatically and uses them for bookkeeping. Generally, I recommend setting participant fields at object instantiation 
and, except perhaps for the `comments` field, never changing them.

#### Saving and loading
  
When we created our participant object, it automatically saved a [JSON](https://www.json.org/json-en.html) 
representation of itself to a file in the `participants` subdirectory, whose path is given by the `path` field. This 
will always happen every time we create a participant object and there is no way to stop it, by design. A participant 
object will also save itself before garbage collection.
  
```python  
del p  # delete the participant 
```

This "autosaving" feature allows expflow to enforce ***Golden Rule #1: A given participant can't be created twice***. An
exception will be raised if you try to create a new participant with the same `participant_id` as an existing 
participant, even if the older participant was not created during the current Python session.

```python
try:
    p = expflow.Participant("example_p1")  # even though we deleted `p`!
    raise RuntimeError("You won't see this message")

except expflow.ParticipantExistsError as er:
    logging.error(er)
```

Sometimes you may need to load a participant, for example to add something to their `comments` field. You can do so 
using the `load` class method, which requires the `participant_id`.

```python
p = expflow.Participant.load("example_p1")
p.comments += "- Here's a comment\n"
p.comments += "- Here's another\n"
del p  # autosave on deletion
```

You can overtly save the participant with the `save` method, but you shouldn't need to. If you want to quickly get at 
the participant data for testing or debugging purposes, you can use the `to_dict` and `to_json` methods. But otherwise,
participant objects will save on garbage collection.

#### Compression

By default, JSON representations of participants are uncompressed, but you can use [gzip](https://www.gzip.org) 
compression instead by setting the optional field `compression` to `True` when creating a new participant or setting the
global variable `expflow.using_compression` to `True` to turn on compresson by default. Compressed files usually much 
smaller, but not human readable, and have the extension `.json.gz` instead of `.json`.

### Experiments and trials

#### Creating experiments

Experiments are represented by the `Experiment` dataclass. You must create an instance of this class each time a new 
participant is about to run an experiment. Experiment objects have two required fields: `participant_id` and  
`experiment_id`. 

```python
e = expflow.Experiment("example_p1", "example_e1")
```

The *combination* of these identifiers must be unique. In other words, a single participant can perform multiple 
different experiments, and multiple different participants can perform the same experiment, but  ***Golden Rule #2: A 
given participant can't perform a given experiment twice.***. You can load an experiment object with an existing 
combination of identifiers.

```python
del e  
try:  
    e = expflow.Experiment("example_p1", "example_e1")  
    raise RuntimeError("You won't see this message")  
except expflow.ExperimentExistsError as er:  
    logging.error(er)  
e = expflow.Experiment.load("example_p1", "example_e1")
```

Under the hood, this is enforced by saving on creation and garbage collection.

You also can't create an experiment if the participant doesn't exist.

```python  
try:  
    _ = expflow.Experiment("example_p2", "example_e1")  
    raise RuntimeError("You won't see this message")  
except expflow.ParticipantDoesNotExistError as er:  
    logging.error(er)
```

Finally, experiments have an optional user-specified field called `trials`, which is discussed in the next section. You 
can set this on instantiation or later via special methods.

#### Creating trials

Experiments contain trials. Trials are represented by instance of the `Trial` dataclass, but unlike participant and 
experiment dataclasses, they can't be saved or loaded individually (maybe in a future version). Expflow doesn't insist 
on trials having unique identifiers or on required fields, either.

There are a number of optional fields:

- `stimulus`
- `response` 
- `trial_number`
- `block_number`
- `condition` 
- `practice`

It should be obvious what each of these is supposed to represent.

Let's create a list of trials.

```python  
trials = [expflow.Trial(trial_number=i) for i in range(3)]  
```  

#### Appending trials to an experiment
  
Inside an experiment object, trials are stored in field called `trials`, which is a list of `Trial` objects. The 
experiment we created currently has an empty `trials` field.  
  
```python  
assert len(e.trials) == 0  
```  
  
This is a good time to bring up ***Golden Rule #3: Run experiments by iterating experiment objects***. Accordingly, `e` 
is iterable and its `__len__` method returns the number of trials it contains.  
  
```python  
assert len(e) == 0  
```  
  
We can append the trials we created to the experiment using the `append_trials` method.  
  
```python  
e.append_trials(trials)  
```  

You can append to or otherwise directly modify `e.trials` **but please don't**, because the `append_trials` method does 
extra things like checks you are actually appending `Trial` instances and saves the experiment object.

After appending, the experiment has three trials.  
  
```python  
assert len(e) == 3  
```  
  
Experiments save themselves after a trial is appended, so if we delete the experiment and reload it, we will see that 
the appended trials are there.  
  
```python  
del e  
e = expflow.Experiment.load("example_p1", "example_e1")
assert len(e) == 3  
```  
  
#### Other manipulations to the trial list

Currently, there are only `append_trials`, `append_trial`, and `insert_trial` methods, but more may be added in future 
versions of expflow.

###  Experiment flow

This section will describe the core features that allows expflow to control experiment flow. First, it is important to 
know about two variables inside experiment objects: the trial index and the status.

#### Trial index

Experiments have a field called `trial_index`, which is automatically managed. Its value is `None` on instantiation, and
becomes an integer when the experiment runs. Predictably, this is used to index the experiment's current position in 
the trial list. User's shouldn't set this field themselves.

#### Statuses
  
Experiments (and trials) have a special `status` property (mirrored by the `current_status` field). Users shouldn't set
this property or its field themselves, but they can read it or test its value with `is_*` boolean properties. 

There are only six possible statuses and only certain status transitions are possible. The possible statuses, their 
meanings, and acceptable transitions are given in the table below.

| Status        | Description                          | Acceptable transitions      |
|---------------| ------------------------------------ |-----------------------------|
| `"pending"`   | Trial is scheduled to run later      | running, skipped            |
| `"running"`   | Trial is running right now           | finished, timed_out, paused |
| `"paused"`    | Trial is temporarily paused          | running                     |
| `"timed_out"` | Trial went on too long and has ended | -                           |
| `"finished"`  | Trial ended as expected              | -                           |
| `"skipped"`   | Trial will not run                   | -                           |

This is designed to conisistent with the common usage of the words. On instantiation, the status of an experiment is 
always `"pending"`. This is natural, because experiments are created before they are run. Pending experiments can be 
changed to `"running"` or `"skipped"`. Running experiments can be changed to `"finished"` if they were completed normally, `"paused"` if they were paused, or `"timed_out"` if they were timed out. Paused experiments must be unpaused (i.e., set back to `"running"`) before they can be `"finished"`. `"finished"`, `"timed_out"`, and `"skipped"` are terminal statuses. Hopefully this all makes intuitive sense.

Individual trials have a status property that behaves in exactly the same way.

As we shall see, experiment and trial statuses are managed automatically as we run an experiment. In fact, this is the
major trick expflow employs to ensure proper flow.
  
#### Running experiments  
  
As per Golden Rule #3, to run an experiment, you iterate over the experiment object, such as in a  `for` loop.
  
```python  
def show_stimulus(stimulus):
	"""Replace this with something that presents stimuli."""
    pass  
  
def get_response(): 
	"""Replace this with something that collects responses."""
    return "response"  
  
for trial in e:

	# do experimental stuff here, for example ...
	show_stimulus(trial.stimulus)  
    trial.response = get_response()
    # ... end of experimental stuff
    
    if not e.is_running:
	    break  
```  
  
This is *almost* a completely normal Python `for` loop. I say almost because it contains an `if` statement that will 
prematurely break the loop if the experiment status is no longer set to `"running"`. This is necessary to catch pauses,
skips, and time outs (discussed later).

If your experiment is embedded within a larger program and it is not convenient or possible to use the `for` syntax, 
you could use `next(e)` instead, but just remember to catch the `StopIteration` exception.

#### Saving data

Notice that in our toy experiment above, the `response` field of the current trial was set to the participant's response
on that trial. How do we make sure those responses are recorded?

Each `trial` in the loop was a reference to the experiment's current trial (also available via `self.current_trial`). 
Therefore, because we set `trial.response` to `"response"`, participant responses are available after iteration (i.e., 
after the experiment has finished).

```python
for trial in e.trials:  # remember Golden Rule #3  
    assert trial.response == "response"
```

Furthermore, experiments save themselves after each iteration and status change, so we have also *serialised* the data 
as well. Let's delete the experiment object and reload it. 
  
```python  
del e  
e = expflow.Experiment.load("example_p1", "example_e1")  
for trial in e.trials: # Golden Rule #3 
    assert trial.response == "response"
```  

The responses were recorded! This is important — it means that expflow automatically stores data across Python sessions
with no extra effort on the part of the user.

#### Pausing

Suppose an experiment is too long to be completed all in one session: we need to pause it and resume it later. The 
following code simulates a pause halfway through an experiment.

```python
p2 = expflow.Participant("example_p2")
trials = [expflow.Trial(trial_number=i) for i in range(10)]
e3 = expflow.Experiment("example_p2", "example_e1", trials=trials)

for trial in e:

	if e.trial_index > 5:
	
		show_stimulus(trial.stimulus)  
	    trial.response = get_response()

	else:
		e.pause()
    
    if not e.is_running:
	    break  

assert e.is_paused
assert e.current_trial.is_paused
```

You can resume a paused experiment by iterating over it again.

```python
for trial in e:

	assert e.trial_index > 5
	
	show_stimulus(trial.stimulus)  
	trial.response = get_response()
    
    if not e.is_running:
	    break
```

#### Timing out

Individual trials or entire experiments may have time limits. If so, you can use the `trial.time_out` and 
`experiment.time_out` methods to time out a trial or experiment, respectively. Timed out trials and experiments cannot 
be resumed (unlike paused trials).

#### Skipping

Sometimes an experiment may skip upcoming trials, or an experiment may be skipped enitrely (if it is part of a batch of
experiments, for example). You can use the `trial.skip` and `experiment.skip` methods to achieve this. You can't skip a
trial or experiment that was already started, nor can you ever
start a skipped trial or experiment.

Experiments don't always present every trial to every participant. Sometimes an experiment may have a stopping rule, 
where some or all remaining trials are skipped due to poor performance, or trial-specific or whole-experiment time 
limits. The statuses `"skipped"` and `"timed_out"` — and their respecitve methods, `skip` and `timeout` (or `time_out`) — exist to deal with these circumstances. You can skip or time out individual trials or entire experiments. Skipped or timed out experiments/trials cannot be rerun afterwards under any circumstances.

#### Duration

Experiments and trials have a  `duration` field that is calculated when the experiment/trial is finished or timed out. 
It represents the total time taken to complete the experiment/trial, minus any time spent in a paused state, in seconds.

#### Crash recovery

Expflow has a rudimentary crash-recovery feature. It doesn't work all the time, but it could save your bacon once in a
while.

Consider this example:

```python
p3 = expflow.Participant("example_p3")
trials = [expflow.Trial(trial_number=i) for i in range(3)]
e2 = expflow.Experiment("example_p3", "example_e1", trials=trials)  

for trial in e3:  
    
    show_stimulus(trial.stimulus)  
    trial.response = get_response()  
    
    break  # <- crash!  

del e3  # <- crash!  

e3 = expflow.Experiment.load("example_p3", "example_e1")  
assert e3.is_paused  
assert e3.current_trial.is_paused
```

Here, we have simulated a computer crash by breaking the trial loop and deleting our experiment object, which is 
approximately what would happen if you encountered an unexpected exception during your experiment. On garbage 
collection, an experiment object will change its status from running to 
paused if necessary, and save itself. Therefore, when this experiment is loaded again, it behaves as if it were paused 
at the point of garbage collection.