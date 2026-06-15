import unittest
from unittest.mock import MagicMock, patch

from school_library_service import list_province_schools, query_province_school_ids


class SchoolLibraryServiceTests(unittest.TestCase):
    def test_query_province_school_ids_empty_without_province(self):
        self.assertEqual(query_province_school_ids(''), set())

    @patch('school_library_service.get_connection')
    def test_list_province_schools_returns_empty_when_no_ids(self, mock_conn):
        connection = MagicMock()
        mock_conn.return_value.__enter__.return_value = connection
        connection.execute.return_value.fetchall.return_value = []
        result = list_province_schools('河南', '本科批', limit=100)
        self.assertEqual(result['list'], [])
        self.assertEqual(result['total'], 0)


if __name__ == '__main__':
    unittest.main()
