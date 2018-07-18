# django-up-to-date

Build and packages check automation for Django projects

## Features

- Run tests, excluding tags `slow` and `selenium`. If they passed
- run all required Django commands necessary after code base updates and
- `touch uwsgi.ini`.
- Log all output to a file or shell.
- Send an e-mail error report if a command exited not with returncode 0 and
  exit with it's returncode.

## Required

- Python 3
- pipenv
- Django (because of the commands)
- `build.py` has to be in a subdirectory of the Django project (designed to be
  used as Git submodule) or the environment variable `DJANGO_PROJECT_PATH` has
  to be set.
- `uwsgi.ini` in the Django project directory
- `config.ini` in the Django project directory:

  ```ini
  [email]
  DEFAULT_FROM_EMAIL: noreply@example.com
  DEFAULT_TO_EMAILS: dev@example.com admin@example.com
  HOST: smtp.example.com
  HOST_USER: noreply@example.com
  HOST_PASSWORD: secret
  # TLS is used to send the e-mails

  [environment]
  DEBUG: false
  # or true
  LOG_PATH: log/dir/
  # can be absolute or relative to the Django project dir
  NAME: Example project

  # optional
  [test]
  SETTINGS: optional.django.test.settings
  ```
