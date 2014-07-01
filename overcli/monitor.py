import logging
import subprocess, shlex
import threading
from datetime import datetime

logger = logging.getLogger(__name__)


class Service(object):
    def __init__(self, period, name, cwd, command):
        """ Define a service to be monitored
        :param period: Test period, seconds
        :type period: int
        :param name: Service name
        :type name: str
        :param cwd: Current working directory
        :type cwd: str
        :param command: Full command path that test service state
        :type command: str
        """
        self.period = period
        self.name = name
        self.cwd = cwd
        self.command = command

        self.lag = 0
        self.last_tested = None

    def __str__(self):
        return self.name

    @property
    def real_period(self):
        """ Real update period, including lags and safety reserves """
        return max(self.period * 0.8 - self.lag * 3.0, 0.0)

    def next_update_in(self, now):
        """ Get the relative time for the next update
        :param now: Current datetime
        :type now: datetime
        :return: Delay, seconds
        :rtype: float
        """
        # Never updated: NOW!
        if self.last_tested is None:
            return 0.0

        # Was updated
        seconds_ago = (now - self.last_tested).total_seconds()
        delay = self.real_period - seconds_ago
        return max(delay, 0.0)  # don't allow it to be negative


    def get_state(self):
        """ Execute plugin and get service's state
        :return: Process state for the API
        :rtype: dict
        :exception OSError: Failed to execute plugin
        """
        # Execute command
        try:
            process = subprocess.Popen(
                shlex.split(self.command),
                cwd=self.cwd,
                stdin=None,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
            process.wait()
        except OSError, e:
            error_msg = u'Failed to execute plugin `{}`: {}'.format(self.name, e.message)
            logger.exception(error_msg)
            return {
                'name': self.name,
                'state': 'UNK',
                'info': error_msg
            }

        # Analyze the result
        try:
            # Info
            info = process.stdout.read()

            # Determine state
            try:
                state = ['OK', 'WARN', 'FAIL', 'UNK'][process.returncode]
            except IndexError:
                logger.error(u'Plugin `{}` failed with code {}: {}'.format(self.name, process.returncode, info))
                state = 'UNK'

            # Finish
            return {
                'name': self.name,
                'state': state,
                'info': info
            }
        finally:
            process.stdout.close()


class ServicesMonitor(object):
    def __init__(self, services):
        """ Monitor for Services
        :param services: List of Services to be monitored
        :type services: list
        """
        self.services = services

        # Measure plugins performance
        self._evaluate_service_lags()

    def _evaluate_service_lags(self):
        """ Measure lag for each service """
        # Worker
        def task(service):
            # Start plugin
            start = datetime.utcnow()
            service.get_state()
            finish = datetime.utcnow()

            # Store the lag
            delta = (finish-start).total_seconds()
            service.lag = delta

            # Ok?
            if service.lag > service.period*0.5:
                logger.warning('Service `{}` execution lag is too high: {}s'.format(service.name))

        # Run
        threads = [threading.Thread(target=task, args=(service,)) for service in self.services]
        for t in threads: t.start()
        for t in threads: t.join()

    def _check_services(self, services):
        """ Check services provided as an argument
        :param services: List of services to test
        :type services: list[Service]
        :return: `services` argument value for reporting
        :rtype: list
        """
        now = datetime.utcnow()

        # Worker
        service_states = []
        def task(service):
            # Add state
            state = service.get_state()
            service_states.append(state)
            logger.debug(u'Check service {}: last checked {} ago, state={}: {}'.format(
                service.name,
                now - service.last_tested if service.last_tested else '(never)',
                state['state'], state['info']
            ))

            # Update timestamp
            service.last_tested = now

        # Run
        threads = [threading.Thread(target=task, args=(service,)) for service in services]
        for t in threads: t.start()
        for t in threads: t.join()

        return service_states

    def sleep_time(self):
        """ Determine how many seconds is it ok to sleep before any service state should be reported
        :rtype: float
        """
        now = datetime.utcnow()
        return min(service.next_update_in(now) for service in self.services)

    def check(self):
        """ Check services whose time has come, once.
        :return: (period, service_states) to be reported to the API
        :rtype: (int, dict)
        """
        # Determine which services to test
        max_lag = max(service.lag for service in self.services)
        now = datetime.utcnow()
        services = [ service
                     for service in self.services
                     if service.next_update_in(now) <= max_lag
        ]
        period = max(service.period for service in services)

        # Test them
        service_states = self._check_services(services)

        # Report
        return int(period), service_states
