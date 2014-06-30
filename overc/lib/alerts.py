import os
import subprocess
import logging

logger = logging.getLogger(__name__)


def list_alert_plugins(plugins_path):
    """ Get the list of available alert plugins
    :param plugins_path: Plugins directory path
    :type plugins_path: str
    :return: List of plugin names (filenames)
    :rtype: list
    """
    return os.listdir(plugins_path)


def execute_alert_plugin(plugins_path, plugin, arguments, message):
    """ Execute an alert plugin
    :param plugins_path: Path to alert plugins
    :type plugins_path: str
    :param plugin: Plugin filename
    :type plugin: str
    :param arguments: Plugin arguments
    :type arguments: list
    :param message: Message to report
    :type message: unicode
    :exception OSError: plugin not found
    :exception subprocess.CalledProcessError: plugin execution error (non-zero return code)
    """
    # Prepare
    #command = shlex.split(plugin + ' ' + arguments)
    command = [plugin] + arguments

    # Execute
    process = subprocess.Popen(
        command,
        cwd=plugins_path,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    process.stdin.write(message)
    process.stdin.close()
    process.wait()


def send_alert_to_subscribers(alertd_path, alerts_config, message):
    """ Fetch notifications config and send messages
    :param alertd_path: Path to "alert.d" folder
    :type alertd_path: str
    :param alerts_config: Alerts config
    :type alerts_config: dict
    :param message: Alert message
    :type message: unicode
    """
    # Send
    plugin_failures = []
    for plugin_name, plugin_args in alerts_config.items():
        try:
            execute_alert_plugin(alertd_path, plugin_args[0], plugin_args[1:], message)
        except Exception as e:
            plugin_failures.append((plugin_name, e))

    # Report plugin errors
    plugin_failures = "\n".join([ 'Alert plugin `{}` failed: {}'.format(plugin_name, e) for plugin_name, e in plugin_failures ])
    for plugin_name, plugin_args in alerts_config.items():
        try:
            execute_alert_plugin(alertd_path, plugin_args[0], plugin_args[1:], plugin_failures)
        except Exception:
            logger.exception('Failed to send fatal plugin notification')
