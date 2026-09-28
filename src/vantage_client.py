import getpass

from vantage6.client import UserClient as Client

def authenticate(config: dict[str, str | int],
                  username: str | None = None,
                  password: str | None = None,
                  mfa_code: str | None = None,
                  private_key_path: str | None = None,
                  use_mfa: bool = True,
                  use_encryption: bool = True,
                  log_level: str = 'debug') -> Client:
    """
    This function authenticates a Vantage6 client.

    It creates a client with the given configuration details, authenticates the client,
    and sets up encryption for the client.

    Parameters:
    config (dict[str, str | int]): An object containing configuration details.
    It should have the following attributes:
        - server_url: The server URL.
        - server_port: The server port.
        - server_api: The server API.
    username (str | None): The username to authenticate with. If not provided, it is
    requested interactively.
    password (str | None): The password to authenticate with. If not provided, it is
    requested interactively.
    mfa_code (str | None): The MFA-token to authenticate with. If not provided, it is
    requested interactively.
    private_key_path (str | None): The path to the organization private key. If not
    provided, it is requested interactively.
    use_mfa (bool): Whether the server requires an MFA-token. Set to False for the
    vantage6 developer network.
    use_encryption (bool): Whether the collaboration is encrypted. Set to False for the
    vantage6 developer network; no private key is requested in that case.
    log_level (str): The log level of the client, e.g. 'debug', 'info' or 'warn'.

    Returns:
        Client: An authenticated client with encryption set up.
    """
    # Create a client
    client = Client(config.get('server_url'),
                    config.get('server_port'),
                    config.get('server_api'),
                    log_level=log_level)

    # Request the private key separately so that the MFA-code does not expire
    if use_encryption:
        if private_key_path is None:
            private_key_path = getpass.getpass("Enter path to organization private key: ")
        # Strip double quotes from the path if users are on Windows and use CTRL+SHIFT+C
        private_key_path = private_key_path.strip('"')
    else:
        private_key_path = None

    if username is None:
        username = input("Enter username: ")
    if password is None:
        password = getpass.getpass("Enter password: ")
    if use_mfa and mfa_code is None:
        mfa_code = getpass.getpass('Enter MFA-token: ')

    # Authenticate the client
    client.authenticate(username=username,
                        password=password,
                        mfa_code=mfa_code)

    # Set up encryption for the client; a private key of None disables encryption
    client.setup_encryption(private_key_file=private_key_path)
    del private_key_path

    return client
