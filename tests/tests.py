import os
import shutil
import subprocess
import sys
import tempfile
import unittest

TEST_PATH = os.path.dirname(os.path.abspath(__file__))

sys.path.append(os.path.dirname(TEST_PATH))

import main  # noqa: E402


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create temp dir
        tmpdir = os.path.join(TEST_PATH, '.temp')
        try:
            temp = tempfile.TemporaryDirectory(dir=tmpdir)
        except FileNotFoundError:
            os.mkdir(tmpdir)
            temp = tempfile.TemporaryDirectory(dir=tmpdir)
        temp_dir = temp.name

        # Duplicate project
        temp_django_dir = os.path.join(temp_dir, 'project')
        shutil.copytree(
            os.path.join(TEST_PATH, 'project'),
            temp_django_dir,
            ignore=shutil.ignore_patterns('.venv'),
        )

        # Define some paths
        cls.temp_log_path = os.path.join(
            temp_django_dir,
            'logs',
            'django_build.log',
        )
        os.mkdir(os.path.dirname(cls.temp_log_path))
        cls.temp_django_dir = temp_django_dir
        cls.temp_uwsgi_path = os.path.join(temp_django_dir, 'uwsgi.ini')
        # Keep the temporary dir as long as the class exists
        cls.temp = temp

        # Initialize Build
        cls.build = main.Build()
        cls.build.project_path = temp_django_dir
        cls.build.test = True

    def tearDown(self):
        try:
            os.remove(self.temp_log_path)
        except FileNotFoundError:
            pass

    def test_debug(self):
        self.assertFalse(self.build.debug)

    def test_log_path(self):
        self.assertEqual(
            self.build.log_path,
            self.temp_log_path,
        )

    def test_uwsgi_path(self):
        self.assertEqual(
            self.build.reload_webserver(),
            self.temp_uwsgi_path,
        )

    def test_send_email(self):
        email = self.build.send_email('Test mail', 'Hi, how are you?')
        self.assertEqual(email['subject'], 'Test mail')
        self.assertEqual(email['from'], 'noreply@example.com')
        self.assertEqual(email['to'], 'dev@example.com, admin@example.com')
        self.assertEqual(email.get_content(), 'Hi, how are you?\n')

    def test_env_in_project(self):
        self.build.sync_packages()
        os.remove(self.temp_log_path)
        self.build.run_command('pipenv', '--venv')
        with open(self.temp_log_path, 'r+') as f:
            self.assertEqual(
                f.readlines()[2],
                os.path.join(self.temp_django_dir, '.venv\n'),
            )

    def test_fail_pipenv(self):
        temp_pipfile_path = os.path.join(self.temp_django_dir, 'Pipfile.lock')
        with open(temp_pipfile_path, 'a') as f:
            f.write('x')
        with self.assertRaises(SystemExit) as cm:
            self.build.sync_packages()
        self.assertNotEqual(cm.exception.code, 0)
        self.assertFalse(os.path.exists(self.temp_uwsgi_path))
        with open(self.temp_log_path, 'r+') as f:
            self.assertNotEqual(f.read(), '')
            f.seek(0)
            self.assertEqual(f.tell(), 0)

        with open(temp_pipfile_path, 'r+') as f:
            f.seek(0, os.SEEK_END)
            position = f.tell() - 2
            f.seek(position, os.SEEK_SET)
            f.truncate()

    def test_fail_collectstatic(self):
        os.environ['TEST_STATIC_URL'] = ''
        self.build.sync_packages()
        with self.assertRaises(SystemExit) as cm:
            self.build.collect_static_files()
        self.assertNotEqual(cm.exception.code, 0)
        os.environ.pop('TEST_STATIC_URL')
        with open(self.temp_log_path, 'r+') as f:
            self.assertNotEqual(f.read(), '')

    def test_fail_tests(self):
        os.environ['LETS_TEST_FAIL'] = '1'
        self.build.sync_packages()
        with self.assertRaises(SystemExit) as cm:
            self.build.run_tests()
        self.assertNotEqual(cm.exception.code, 0)
        os.environ.pop('LETS_TEST_FAIL')
        with open(self.temp_log_path, 'r+') as f:
            self.assertNotEqual(f.read(), '')

    def test_fail_migrations(self):
        os.environ['TEST_DATABASE'] = '1'
        with self.assertRaises(SystemExit) as cm:
            self.build.migrate_database()
        self.assertNotEqual(cm.exception.code, 0)
        os.environ.pop('TEST_DATABASE')
        text = 'You might solve migration issues by switching to your '
        with open(self.temp_log_path, 'r+') as f:
            self.assertIn(text, f.read())

    def test_pass(self):
        with self.assertRaises(SystemExit) as cm:
            self.build.run()
        if cm.exception.code != 0:
            print(60 * '#')
            with open(self.temp_log_path, 'r+') as f:
                print(f.read())
            print(60 * '#')
        self.assertEqual(cm.exception.code, 0)
        self.assertTrue(os.path.exists(self.temp_uwsgi_path))
        os.remove(self.temp_uwsgi_path)

    def test_pass_second_time(self):
        os.environ['DJANGO_PROJECT_PATH'] = self.temp_django_dir
        result = subprocess.run(
            ('python3', os.path.join(os.path.dirname(TEST_PATH), 'build.py')),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(os.path.exists(self.temp_uwsgi_path))
        os.environ.pop('DJANGO_PROJECT_PATH')
        with self.assertRaises(SystemExit) as cm:
            self.build.run()
        self.assertEqual(cm.exception.code, 0)
        os.remove(self.temp_uwsgi_path)
