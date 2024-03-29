import dataclasses
import logging
import tempfile
import pathlib

from datetime import date, datetime as dt
from unittest import TestCase

from logmixin import LogMixin

from expflow import expflow


class TestFilesAndPaths(TestCase, LogMixin):

    tmpdir = tempfile.TemporaryDirectory()
    logging.basicConfig(level=logging.DEBUG)

    def test__get_pdir(self):
        pdir = expflow._get_pdir()
        self.assertIsInstance(pdir, pathlib.Path)
        self.assertTrue(pdir.exists())

    def test__get_edir(self):
        edir = expflow._get_edir()
        self.assertIsInstance(edir, pathlib.Path)
        self.assertTrue(edir.exists())

    def test__get_tdir(self):
        gdir = expflow._get_tdir()
        self.assertIsInstance(gdir, pathlib.Path)
        self.assertTrue(gdir.exists())

    def test__get_ldir(self):
        pdir = expflow._get_ldir()
        self.assertIsInstance(pdir, pathlib.Path)
        self.assertTrue(pdir.exists())

    def test__get_trashdir(self):
        pdir = expflow._get_trashdir()
        self.assertIsInstance(pdir, pathlib.Path)
        self.assertTrue(pdir.exists())

    def test_set_expflow_dir(self):
        expflow.set_expflow_dir(self.tmpdir.name)
        self.assertEqual(
            expflow._get_pdir(), pathlib.Path(self.tmpdir.name, "Participants"),
        )
        self.assertEqual(
            expflow._get_edir(), pathlib.Path(self.tmpdir.name, "Experiments"),
        )
        self.assertEqual(
            expflow._get_tdir(), pathlib.Path(self.tmpdir.name, "Trials"),
        )
        self.assertEqual(
            expflow._get_ldir(), pathlib.Path(self.tmpdir.name, "Logs"),
        )
        self.assertEqual(
            expflow._get_trashdir(), pathlib.Path(self.tmpdir.name, "Trash"),
        )
        self.assertTrue(expflow._get_pdir().exists())
        self.assertTrue(expflow._get_edir().exists())
        self.assertTrue(expflow._get_tdir().exists())
        self.assertTrue(expflow._get_ldir().exists())
        self.assertTrue(expflow._get_trashdir().exists())


class TestParticipant(TestCase, LogMixin):

    def test_participant(self):
        p = expflow.Participant(participant_id="test1")
        self.assertEqual(p.participant_id, "test1")

    def test_participant_class_is_json_serialisable(self):
        p = expflow.Participant("test2")
        j = p.to_json()
        self.get_logger().debug(j)
        a = expflow.Participant.from_json(j)
        self.assertTrue(p == a)
        self.assertTrue(p.datetime_last_saved == a.datetime_last_saved)
        a.save()
        self.assertTrue(a.datetime_last_saved > p.datetime_last_saved)

    def test_participant_custom_subclass(self):

        @dataclasses.dataclass
        class CustomParticipant(expflow.Participant):
            new_field: str = ""

        p = CustomParticipant(participant_id="test3", new_field="test")
        self.assertEqual(p.participant_id, "test3")
        j = p.to_json()
        self.get_logger().debug(j)
        a = CustomParticipant.from_json(j)
        self.assertTrue(p == a)
        self.assertRaises(expflow.WrongClassError, expflow.Participant.from_json, j)

    def test_save_and_load(self):
        p = expflow.Participant(participant_id="test4")
        p.save()
        p2 = expflow.Participant.load(participant_id="test4")
        self.assertEqual(p, p2)
        self.assertEqual(p.datetime_last_saved, p2.datetime_last_saved)
        p2.save()
        self.assertGreater(p2.datetime_last_saved, p.datetime_last_saved)

    def test_delete(self):
        p = expflow.Participant(participant_id="test5")
        p.save()
        p2 = expflow.Participant.load(participant_id="test5")
        p.delete()
        del p
        p2.save()
        p2.delete()
        self.assertRaises(FileNotFoundError, expflow.Participant.load, "test5")


class TestTrial(TestCase, LogMixin):
    def test_trial(self):
        t = expflow.Trial()
        self.assertEqual(t.stimulus, None)

    def test_trial_statuses(self):
        t = expflow.Trial()
        self.assertEqual(t.status, "pending")
        self.assertTrue(t.is_pending)
        t.run()
        self.assertEqual(t.status, "running")
        self.assertTrue(t.is_running)
        t.pause()
        self.assertEqual(t.status, "paused")
        self.assertTrue(t.is_paused)
        t.resume()
        self.assertEqual(t.status, "running")
        self.assertTrue(t.is_running)
        t.finish()
        self.assertEqual(t.status, "finished")
        self.assertTrue(t.is_finished)
        self.assertRaises(ValueError, t.run)
        self.get_logger().debug(t.to_json())
        self.assertGreater(t.duration, 0)


class TestExperiment(TestCase, LogMixin):

    def show_stimulus(self, stimulus):
        """Replace this with something that shows the stimulus."""
        pass

    def get_response(self):
        """Replace this with something that gathers user input."""
        return "response"

    def test__p_doesnt_exist(self):
        self.assertRaises(
            expflow.ParticipantDoesNotExistError,
            expflow.Experiment,
            "participant_id_1",
            "experiment_id_1",
        )

    def test_same_experiment_id(self):
        p = expflow.Participant("participant_id_1a")
        e = expflow.Experiment("participant_id_1a", "experiment_id_1a")
        self.assertRaises(
            expflow.ExperimentExistsError,
            expflow.Experiment,
            "participant_id_1a",
            "experiment_id_1a",
        )

    def test_experiment(self):
        p = expflow.Participant("participant_id_1")
        e = expflow.Experiment("participant_id_1", "experiment_id_1")
        self.assertEqual(e.participant_id, "participant_id_1")
        self.assertEqual(e.experiment_id, "experiment_id_1")
        self.assertEqual(e.trials, [])

    def test_experiment_statuses(self):
        p = expflow.Participant("participant_id_2")
        e = expflow.Experiment("participant_id_2", "experiment_id_2")
        self.assertEqual(e.status, "pending")
        self.assertTrue(e.is_pending)
        e.run()
        self.assertEqual(e.status, "running")
        self.assertTrue(e.is_running)
        e.pause()
        self.assertEqual(e.status, "paused")
        self.assertTrue(e.is_paused)
        e.resume()
        self.assertEqual(e.status, "running")
        self.assertTrue(e.is_running)
        e.finish()
        self.assertEqual(e.status, "finished")
        self.assertTrue(e.is_finished)
        self.assertRaises(ValueError, e.run)
        self.get_logger().debug(e.to_json())
        self.assertGreater(e.duration, 0)

    def test_experiment_statuses_2(self):
        expflow.Participant("participant_id_3")
        trials = [expflow.Trial() for _ in range(3)]
        e = expflow.Experiment("participant_id_3", "experiment_id_3", trials=trials)
        e.run()
        e.time_out()
        self.assertEqual(e.status, "timed_out")
        self.get_logger().debug(e.to_json())

    def test_experiment_statuses_3(self):
        expflow.Participant("participant_id_6")
        trials = [expflow.Trial() for _ in range(3)]
        e = expflow.Experiment("participant_id_6", "experiment_id_6", trials=trials)
        e.skip()
        self.assertEqual(e.status, "skipped")
        self.get_logger().debug(e.to_json())

    def test_experiment_statuses_4(self):
        expflow.Participant("participant_id_7")
        trials = [expflow.Trial(trial_number=i) for i in range(3)]
        e = expflow.Experiment("participant_id_7", "abcd", trials=trials)
        self.assertTrue(e.is_pending)
        for trial in e:
            self.assertTrue(e.is_running)
            self.show_stimulus(trial.stimulus)
            trial.response = self.get_response()
            if not e.is_running:
                break
        self.assertTrue(e.is_finished)
        self.get_logger().debug(e.to_json())

    def test_experiment_statuses_5(self):
        expflow.Participant("participant_id_8")
        trials = [expflow.Trial(trial_number=i) for i in range(10)]
        e = expflow.Experiment("participant_id_8", "abcd", trials=trials)
        self.assertTrue(e.is_pending)
        for trial in e:
            self.assertTrue(e.is_running)
            self.show_stimulus(trial.stimulus)
            trial.response = self.get_response()
            if e.trial_index == 4:
                e.pause()
            if not e.is_running:
                break
        self.assertTrue(e.is_paused)
        self.assertEqual(e.trial_index, 4)
        self.get_logger().debug(e.to_json())

    def test_experiment_statuses_6(self):
        expflow.Participant("participant_id_9")
        trials = [expflow.Trial(trial_number=i) for i in range(10)]
        e = expflow.Experiment("participant_id_9", "abcd", trials=trials)
        self.assertTrue(e.is_pending)
        for trial in e:
            self.assertTrue(e.is_running)
            self.show_stimulus(trial.stimulus)
            trial.response = self.get_response()
            if e.trial_index == 4:
                e.pause()
            if not e.is_running:
                break
        self.assertTrue(e.is_paused)
        self.assertEqual(e.trial_index, 4)
        self.get_logger().debug(e.to_json())
        for trial in e:
            self.assertTrue(e.is_running)
            self.show_stimulus(trial.stimulus)
            trial.response = self.get_response()
            self.assertGreaterEqual(e.trial_index, 4)

    def test_experiment_statuses_7(self):
        expflow.Participant("participant_id_10")
        trials = [expflow.Trial(trial_number=i) for i in range(10)]
        e = expflow.Experiment("participant_id_10", "abcd", trials=trials)
        self.assertTrue(e.is_pending)
        for trial in e:
            self.assertTrue(e.is_running)
            self.show_stimulus(trial.stimulus)
            trial.response = self.get_response()
            if e.trial_index == 4:
                e.time_out()
            if not e.is_running:
                break
        self.assertTrue(e.is_timed_out)
        self.assertRaises(ValueError, next, e)

    def test_experiment_statuses_8(self):
        expflow.Participant("participant_id_11")
        trials = [expflow.Trial(trial_number=i) for i in range(10)]
        e = expflow.Experiment("participant_id_11", "abcd", trials=trials)
        for trial in e:
            self.assertTrue(e.is_running)
            self.show_stimulus(trial.stimulus)
            trial.response = self.get_response()
            if e.trial_index == 4:
                e.pause()
            if not e.is_running:
                break
        del e
        e = expflow.Experiment.load("participant_id_11", "abcd")
        self.assertTrue(e.is_paused)
        self.assertEqual(e.trial_index, 4)
        for trial in e:
            self.assertTrue(e.is_running)
            self.show_stimulus(trial.stimulus)
            trial.response = self.get_response()
            self.assertGreaterEqual(e.trial_index, 4)
        self.assertTrue(e.is_finished)

    def test_compression(self):
        expflow.using_compression = True
        p = expflow.Participant("participant_id_z_1")
        e = expflow.Experiment("participant_id_z_1", "experiment_id_4")
        self.assertTrue(str(p.path).endswith(".gz"))
        self.assertTrue(str(e.path).endswith(".gz"))
        expflow.using_compression = False
        p = expflow.Participant("participant_id_z_2")
        e = expflow.Experiment("participant_id_z_2", "experiment_id_4")
        self.assertTrue(str(p.path).endswith(".json"))
        self.assertTrue(str(e.path).endswith(".json"))

    def test_dob(self):
        d = date(1990, 1, 1)
        p = expflow.Participant("participant_id_x4", dob=d)
        self.assertEqual(p.dob, d)
        del p
        p = expflow.Participant.load("participant_id_x4")
        self.assertEqual(p.dob, d)

    def test_get_participated_in(self):
        p = expflow.Participant("participant_id_x5")
        e = expflow.Experiment("participant_id_x5", "experiment_id_5")
        self.assertEqual(expflow.get_participated_in(p.participant_id), [e.experiment_id])

    def test_experiment_delete(self):
        p = expflow.Participant("participant_id_x6")
        e = expflow.Experiment("participant_id_x6", "experiment_id_6")
        self.assertTrue(e.path.exists())
        p.delete()
        e.delete()
        self.assertFalse(e.path.exists())