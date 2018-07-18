import datetime
import os
import smtplib
import subprocess
import sys
from configparser import ConfigParser
from email.message import EmailMessage
from pathlib import Path

SEPERATOR = '\n########## {} {}\n'


class Base:
    project_path = os.environ.get(
        'DJANGO_PROJECT_PATH',
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    test = False

    @property
    def config(self):
        try:
            return self._config
        except AttributeError:
            self._config = ConfigParser(interpolation=None)
            self._config.read(os.path.join(self.project_path, 'config.ini'))
            return self._config

    @property
    def debug(self):
        return self.config.getboolean('environment', 'debug')

    @property
    def name(self):
        return self.config.get('environment', 'NAME')

    @property
    def log_path(self):
        path = self.config.get('environment', 'LOG_PATH')
        if not os.path.isabs(path):
            path = os.path.join(self.project_path, path)
        return os.path.join(path, self.log_file)

    def run_command(self, *args, exit=True, input=None):
        """
        Runs a command, logs result and informs about errors.
        """
        result = subprocess.run(
            args,
            input=input,
            cwd=self.project_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Logging
        if self.debug:
            sys.stdout.write(result.stdout.decode() + '\n')
            sys.stderr.write(result.stderr.decode() + '\n')
        else:
            with open(self.log_path, 'a+b') as log_file:
                log_file.write(60 * b'#' + b'\nstdout:\n')
                log_file.write(result.stdout)
                log_file.write(60 * b'#' + b'\nstderr:\n')
                log_file.write(result.stderr)

        # Error handling
        try:
            result.check_returncode()
        except subprocess.CalledProcessError as e:
            migration_info = (
                'You might solve migration issues by switching to your '
                'last git branch/commit where your database/migrations '
                'worked and search for the last migration of the app '
                'where the migration just failed which exists in both '
                'branches. '
                'Then you `cd` to the django folder and run '
                '`pipenv run python manage.py migrate <app> <migration>` '
                'where <migration> is the unique beginning of the '
                'migration py file, e.g. "0003".\n'
                '(Note that this may result in data loss in the '
                'changed fields!)\n'
                'After a successful migration you switch branches '
                'again and run build.py a second time.'
            )
            if exit:
                if 'migrate' in args:
                    # Solution hint for failed migrations
                    if self.debug:
                        sys.stderr.write(migration_info)
                    else:
                        with open(self.log_path, 'a+') as log_file:
                            log_file.write(migration_info)

                if not self.debug:
                    # Send fail notification
                    self.send_email(
                        subject='Build failed: ()'.format(self.name),
                        content='\n\n'.join((
                            str(e),
                            '{} ({})'.format(self.name, self.project_path),
                            60 * '#' + '\nstdout:',
                            result.stdout.decode(),
                            60 * '#' + '\nstderr:',
                            result.stderr.decode(),
                        )),
                    )
                # Exit
                sys.exit(e.returncode)
        return result

    def send_email(self, subject, content):
        email = EmailMessage()
        email.set_content(content)
        email['Subject'] = subject
        email['From'] = self.config.get('email', 'DEFAULT_FROM_EMAIL')
        to = self.config.get('email', 'DEFAULT_TO_EMAILS')
        email['To'] = to.replace(' ', ', ')
        if self.test:
            return email
        server = smtplib.SMTP()
        server.connect(self.config.get('email', 'HOST'), 587)
        server.starttls()
        server.login(
            self.config.get('email', 'HOST_USER'),
            self.config.get('email', 'HOST_PASSWORD'),
        )
        server.send_message(email)
        server.quit()


class Build(Base):
    """
    Automation for commands when new source code arrived.
    """
    beginn = SEPERATOR.format('build', datetime.datetime.now())
    log_file = 'django_build.log'
    python = '.venv/bin/python'

    def run(self):
        """
        Runs all build commands.
        """
        if self.debug:
            sys.stdout.write(self.beginn)
        else:
            with open(self.log_path, 'a+') as log_file:
                log_file.write(self.beginn)

        self.sync_packages()
        # Try to collect static files
        self.collect_static_files(dry=True)
        self.run_tests()
        self.migrate_database()
        if not self.debug:
            # TODO Schedule to --clear it from time to time
            self.collect_static_files()
            self.reload_webserver()
        sys.exit(0)

    def sync_packages(self):
        """
        Updates packages.
        """
        os.environ['PIPENV_VENV_IN_PROJECT'] = '1'
        # Don't install binary packages. Needed for psycopg2==2.7
        os.environ['PIP_NO_BINARY'] = 'psycopg2'
        if self.debug:
            self.run_command('pipenv', 'sync', '--dev')
        else:
            self.run_command('pipenv', 'sync')
        # Clean up unneeded packages
        self.run_command('pipenv', 'clean')

    def collect_static_files(self, dry=False):
        """
        Collects static files.
        """
        if dry:
            args = ('--dry-run',)
        else:
            args = ()
        self.run_command(
            self.python,
            'manage.py',
            'collectstatic',
            '--noinput',
            '-v',
            '0',
            *args,
        )

    def run_tests(self):
        """
        Runs tests. Trys a second time with a fresh database after a failure.
        """
        # You have to run tests from the project directory
        # See https://stackoverflow.com/q/29661112
        settings = self.config.get('test', 'SETTINGS', fallback=None)
        if settings:
            args = ('--settings', settings)
        else:
            args = ()
        result = self.run_command(
            self.python,
            'manage.py',
            'test',
            '-k',
            '--exclude-tag',
            'slow',
            '--exclude-tag',
            'selenium',
            '--noinput',
            *args,
            exit=False,
        )
        try:
            result.check_returncode()
        except subprocess.CalledProcessError:
            # Sometimes it helps to just use a fresh database
            self.run_command(
                self.python,
                'manage.py',
                'test',
                '--exclude-tag',
                'slow',
                '--exclude-tag',
                'selenium',
                *args,
                input=b'yes',
            )

    def migrate_database(self):
        """
        Runs database migrations.
        """
        self.run_command(self.python, 'manage.py', 'migrate', '--noinput')

    def reload_webserver(self):
        """
        Touches uwsgi.ini (to restart uWSGI).
        """
        path = os.path.join(self.project_path, 'uwsgi.ini')
        Path(path).touch()
        return path


class Checks(Base):
    """
    A wrapper around checks with e-mail notification in case of issues.
    """
    log_file = 'django_safety.log'

    def safety(self):
        """
        Looks for packages with known security vulnerabilities.
        """
        self.run_command('pipenv', 'check')
