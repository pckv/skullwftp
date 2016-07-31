""" Dette er selveste skullWFTP
"""

import socket
import ftplib
import shlex
from collections import namedtuple
from functools import wraps
import inspect


commands = []
Command = namedtuple("Command", "name function usage description alias require_login")

running = True  # Når denne er False vil programmet slutte å kjøre


def command(name: str=None, alias: str=None, usage=None, require_login=False):
    """ Legger til en command. Eksempel:

        @command()
        def cd(path):
            print("going to", path)
    """
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            if require_login and not check_logged_in():
                return

            func(*args, **kwargs)

        cmd_name = name or func.__name__

        signature = inspect.signature(func)
        cmd_usage = [cmd_name]

        # Formater usage slik at den er lik funksjonen
        for param in signature.parameters.values():
            cmd_usage.append("<" + param.name + ">")

        commands.append(Command(
            name=cmd_name.lower(),
            function=wrapped,
            usage=(cmd_name + " " + usage) if usage else " ".join(cmd_usage),
            description=inspect.cleandoc(func.__doc__) if func.__doc__ else "Ingen beskrivelse.",
            alias=alias.lower().split() if alias else [],
            require_login=require_login
        ))

        return wrapped

    return decorator


def get_command(name: str):
    """ Finn en command med gitt navn. """
    for cmd in commands:
        # Vi skjekker med lowercase for å være vennlig
        if cmd.name == name.lower() or name.lower() in cmd.alias:
            return cmd

    return None


def parse_command(text: str):
    """ Parse en command. Vi gjør altså tekst om til en funksjon. """
    # Først splitter vi argumentene slik at vi deler opp f.eks "cd home" til "cd" og "home"
    args = shlex.split(text)

    # Så skjekker vi om vi har et argument
    cmd = get_command(args[0])

    # Det er ingen command med det gitte navnet så vi bare returnerer en feilmelding
    if cmd is None:
        return "Det finnes ingen slik command."

    # Vi har commanden, så vi skal bare ploppe alle argumentene inn i funksjonen
    try:
        cmd.function(*args[1:])
    except TypeError:
        print(cmd.usage)


@command(name="exit", alias="quit stop")
def cmd_exit():
    """ Avslutter skullWFTP. """
    global running, logged_in

    if logged_in:
        ftp.quit()
        logged_in = False

    running = False


@command(alias="say")
def echo(*text):
    """ Skriver litt tekst. """
    print(" ".join(text))


@command(name="help", alias="?")
def cmd_help(name):
    """ Viser hjelp. """
    cmd = get_command(name)

    if cmd:
        print(cmd.usage, cmd.description, sep=" : ")

        if cmd.alias:
            print("Alias:", ", ".join(cmd.alias))
    else:
        print("Kommando {} eksisterer ikke.".format(name))


# FTP relatert
ftp = ftplib.FTP()
logged_in = False


def check_logged_in():
    """ Returnerer True/False og printer ved False. """
    if not logged_in:
        print("Du er ikke logget inn på noen FTP server.")
        return False

    return True


@command(alias="connect", usage="<host>:[port]")
def login(host_str):
    """ Opprett forbinelse til en FTP server. """
    global logged_in

    if logged_in:
        print("Du er allerede logget inn.")
        return

    # Splitt den gitte hosten med kolon for å separere IP med port
    values = host_str.split(":")
    host = values[0]
    port = values[1] if len(values) > 1 else 21

    # Koble til med host og port
    try:
        ftp.connect(host, port, timeout=10)
    except socket.timeout:
        print("Tok for lang tid til å etablere en kobling.")
        return
    except socket.gaierror:
        print("Kunne ikke finne host.")
        return

    while True:
        # Spør om brukernavn og passord
        user = input("Brukernavn: ")
        pwd = input("Passord: ")

        # Login med en bruker
        try:
            ftp.login(user, pwd)
        except ftplib.error_perm:
            print("Brukernavn eller passord er feil. Prøv igjen.")
        except ConnectionAbortedError:
            print("Verten avslo din forespørsel.")
        except KeyboardInterrupt:
            break
        else:
            ftp.user = user
            logged_in = True

            print("Koblet til {}".format(host_str), ftp.getwelcome(), sep="\n\n", end="\n\n")
            break


@command(alias="disconnect", require_login=True)
def logout():
    """ Koble fra FTP serveren. """
    global logged_in

    ftp.quit()
    logged_in = False


@command(require_login=True)
def cd(path):
    """ Hopp til en mappe. """
    ftp.cwd(path)


@command(alias="dir l list files", require_login=True)
def ls(path=None):
    """ Se filene i gjeldene eller spesifisert mappe. """
    ftp.dir(path)


@command(alias="rename", require_login=True)
def ren(target, name):
    """ Gi nytt navn til en fil eller mappe. """
    try:
        ftp.rename(target, name)
    except ftplib.error_perm:
        print("Tilgang avvist.")


def main():
    """ Gjør hele skiten. """
    print("Velkommen.\n")

    while running:
        try:
            cmd = input(("skullWFTP" if not logged_in else "{0.user}@{0.host}:{1}".format(ftp, ftp.pwd())) + " $ ")
        except (KeyboardInterrupt, SystemExit):
            if logged_in:
                ftp.quit()
        else:
            if cmd:
                parse_command(cmd)


# Dette betyr bare at vi skal kjøre de gangene programmet faktisk starter
if __name__ == "__main__":
    main()
