import unittest
from pathlib import Path

from deep_tests.contract_model import Command, IdempotencyConflict, ReferenceStore, generate_valid_trace, replay


class CounterpartTipHardeningTests(unittest.TestCase):
    def test_duplicate_create_is_exactly_once(self) -> None:
        store = ReferenceStore()
        command = Command("create", "entity-a", "value", "create-a")
        first = store.apply(command)
        duplicate = store.apply(command)
        self.assertEqual(first, duplicate)
        self.assertEqual(store.revision, 1)

    def test_idempotency_key_stays_bound_to_original_intent(self) -> None:
        store = ReferenceStore()
        store.apply(Command("create", "entity-a", "one", "key-1"))
        store.apply(Command("update", "entity-a", "two", "key-2"))
        with self.assertRaises(IdempotencyConflict):
            store.apply(Command("update", "entity-a", "three", "key-1"))

    def test_large_trace_converges_across_duplicate_schedules(self) -> None:
        commands = generate_valid_trace(20260914, steps=600)
        baseline = replay(commands, duplicate_every=0)
        for interval in (3, 5, 7, 11):
            with self.subTest(interval=interval):
                self.assertEqual(baseline.snapshot(), replay(commands, duplicate_every=interval).snapshot())

    def test_zed_pkg_test_script_exercises_tests_and_repository_verifier(self) -> None:
        text = Path(".zpkg.toml").read_text()
        self.assertIn("unittest discover", text)
        self.assertIn("verify_repository.py", text)


if __name__ == "__main__":
    unittest.main()
