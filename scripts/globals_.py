"""
Globals file for zsnapd
"""

from magcode.core.globals_ import settings

# settings for where files are
settings['config_dir'] = '/etc/zsnapd'
settings['log_dir'] = '/var/log/zsnapd'
settings['run_dir'] = '/run'
settings['config_file'] = settings['config_dir'] + '/' + 'process.conf'
# Zsnapd only uses one daemon
settings['pid_file'] = settings['run_dir'] + '/' + 'zsnapd.pid'
#settings['log_file'] = settings['log_dir'] \
#        + '/' + settings['process_name'] + '.log'
settings['log_file'] = ''
settings['panic_log'] = settings['log_dir'] \
        + '/' + settings['process_name'] + '-panic.log'
settings['syslog_facility'] = ''

# zsnapd.py
# Dataset config file
settings['dataset_config_file'] = settings['config_dir'] \
        + '/' + 'datasets.conf'
# Dataset group config file
settings['dataset_group_config_file'] = settings['config_dir'] \
        + '/' + 'dataset-groups.conf'
# Print debug mark
settings['debug_mark'] = False
# Number of seconds we wait while looping in main loop...
settings['sleep_time'] = 3 # seconds
settings['debug_sleep_time'] = 20 # seconds


