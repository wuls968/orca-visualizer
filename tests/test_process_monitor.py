import unittest

from orca_viz.process_monitor import ProcessRecord, _classify_record, parse_elapsed_seconds, process_dataframe


class ProcessMonitorTests(unittest.TestCase):
    def test_parse_elapsed_seconds(self) -> None:
        self.assertEqual(parse_elapsed_seconds("00:42"), 42)
        self.assertEqual(parse_elapsed_seconds("03:05:07"), 11107)
        self.assertEqual(parse_elapsed_seconds("01-02:03:04"), 93784)

    def test_orca_process_is_classified_as_suspicious(self) -> None:
        record = _classify_record(
            pid=123,
            ppid=1,
            cpu_percent=88.0,
            memory_percent=12.5,
            elapsed="02:15:00",
            command="/opt/orca/orca myjob.inp",
        )

        self.assertEqual(record.category, "orca")
        self.assertEqual(record.risk, "high")
        self.assertTrue(record.resident)
        self.assertIn("orca_related", record.reasons)

    def test_process_dataframe_filters(self) -> None:
        records = [
            ProcessRecord(
                pid=1,
                ppid=0,
                cpu_percent=0.2,
                memory_percent=0.1,
                elapsed="00:10",
                elapsed_seconds=10,
                executable="python3",
                command="python3 app.py",
                category="python",
                risk="low",
                resident=False,
                system_service=False,
                self_related=True,
                reasons=[],
            ),
            ProcessRecord(
                pid=2,
                ppid=1,
                cpu_percent=55.0,
                memory_percent=9.0,
                elapsed="03:20:00",
                elapsed_seconds=12000,
                executable="orca",
                command="/opt/orca/orca job.inp",
                category="orca",
                risk="high",
                resident=True,
                system_service=False,
                self_related=False,
                reasons=["orca_related", "resident"],
            ),
        ]

        dataframe = process_dataframe(
            records,
            include_command=True,
            hide_self_related=True,
            hide_system_services=False,
            only_suspicious=True,
        )
        self.assertEqual(len(dataframe), 1)
        self.assertEqual(dataframe.iloc[0]["process"], "orca")


if __name__ == "__main__":
    unittest.main()
