import unittest

from jarvis.core.stop_controller import StopController


class StopControllerTests(unittest.TestCase):
    def test_stop_sets_shared_cancellation_event_and_reset_clears_it(self) -> None:
        controller = StopController()

        self.assertFalse(controller.is_stopped)
        self.assertFalse(controller.cancellation_event.is_set())

        controller.stop()

        self.assertTrue(controller.is_stopped)
        self.assertTrue(controller.cancellation_event.is_set())

        controller.reset()

        self.assertFalse(controller.is_stopped)


if __name__ == "__main__":
    unittest.main()
