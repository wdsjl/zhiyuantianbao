import unittest

from student_report_service import build_profile_snapshot, profile_snapshot_matches_student


class StudentReportSnapshotTests(unittest.TestCase):
    def test_snapshot_matches_current_student(self):
        profile = {
            'province': '河南',
            'targetBatch': '本科批',
            'subjectCombination': '物理,化学,生物',
            'score': 650,
            'rank': 12000,
        }
        snapshot = build_profile_snapshot(profile)
        student = {
            'province': '河南',
            'target_batch': '本科批',
            'subject_combination': '物理,化学,生物',
            'score': 650,
            'rank': 12000,
        }
        self.assertTrue(profile_snapshot_matches_student(snapshot, student))

    def test_snapshot_mismatch_when_rank_changes(self):
        snapshot = build_profile_snapshot({
            'province': '河南',
            'targetBatch': '本科批',
            'subjectCombination': '物理,化学,生物',
            'score': 650,
            'rank': 12000,
        })
        student = {
            'province': '河南',
            'target_batch': '本科批',
            'subject_combination': '物理,化学,生物',
            'score': 650,
            'rank': 8000,
        }
        self.assertFalse(profile_snapshot_matches_student(snapshot, student))


if __name__ == '__main__':
    unittest.main()
