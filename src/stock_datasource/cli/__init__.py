"""CLI subcommand modules for stock_datasource.

Provides setup wizard, doctor, server management, and config management commands.
"""


def register_commands(cli_group):
    """Register all CLI subcommand groups onto the main Click group.

    Args:
        cli_group: The root Click group from cli.py
    """
    from .setup_wizard import setup
    from .doctor import doctor
    from .server_manager import server
    from .config_manager import config

    cli_group.add_command(setup)
    cli_group.add_command(doctor)
    cli_group.add_command(server)
    cli_group.add_command(config)
