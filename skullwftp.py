""" Dette er selveste skullWFTP
"""

import socket
import ftplib
import shlex
from collections import namedtuple
from functools import wraps
import inspect


commands = []
Command = namedtuple("Command", "name function usage description alias require_login require_arg")

running = True  # Når denne er False vil programmet slutte å kjøre


def command(name: str=None, alias: str=None, usage: str=None, description: str=None,
            require_login: bool=False, require_arg: bool=False):
    """ Legger til en command. Eksempel:

        @command()
        def cd(path):
            print("going to", path)
    """
    def decorator(func):
        cmd_name = name or func.__name__
        signature = inspect.signature(func)
        cmd_usage = [cmd_name]

        # Formater usage slik at den er lik funksjonen
        for i, param in enumerate(signature.parameters.values()):
            # Sett navnet til argumentet
            arg_name = param.name
            if usage is not None:
                if len(usage.split()) > i:
                    usage_arg = usage.split()[i]

                    # Vi vil ha den til å være PRIKK LIK om usage inneholder en [ eller <
                    if "<" in usage_arg or "[" in usage_arg:
                        cmd_usage.append(usage_arg)
                        continue

                    arg_name = usage_arg

            if param.default is param.empty or require_arg:
                cmd_usage.append("<" + arg_name + ">")
            else:
                cmd_usage.append("[" + arg_name + "]")
        cmd_usage = " ".join(cmd_usage)

        @wraps(func)
        def wrapped(*args, **kwargs):
            if require_login and not check_logged_in():
                return

            if require_arg and not args and not kwargs:
                print(cmd_usage)
                return

            func(*args, **kwargs)

        commands.append(Command(
            name=cmd_name.lower(),
            function=wrapped,
            usage=cmd_usage,
            description=description or (inspect.cleandoc(func.__doc__) if func.__doc__ else "Ingen beskrivelse."),
            alias=alias.lower().split() if alias else [],
            require_login=require_login,
            require_arg=require_arg
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
    except ftplib.all_errors as e:
        print(e)


@command(name="exit", alias="quit stop")
def cmd_exit():
    """ Avslutter skullWFTP. """
    global running, logged_in

    # Logg ut dersom vi er innlogget
    if logged_in:
        ftp.quit()
        logged_in = None

    running = False


@command(alias="say")
def echo(*text):
    """ Skriver text. """
    print(" ".join(text))


@command(name="help", alias="?", usage="command")
def cmd_help(name=None):
    """ Viser hjelp. """
    if name is None:
        print("\nKommandoer:")

        # Vis alle kommandoer
        max_length = len(max(cmd.usage for cmd in commands)) + 1
        for cmd in commands:
            print("{cmd.usage: <{spacing}} : {cmd.description}".format(cmd=cmd, spacing=max_length))
    else:
        # Vis hjelp til gitt kommando
        cmd = get_command(name)

        if cmd:
            print(cmd.usage, cmd.description, sep=" : ")

            if cmd.alias:
                print("Alias:", ", ".join(cmd.alias))
        else:
            print("Kommando {} eksisterer ikke.".format(name))


# FTP relatert
ftp = ftplib.FTP()
logged_in = None
prompt = "{user}@{host}:{dir}"


def check_logged_in():
    """ Returnerer True/False og printer ved False. """
    if logged_in is None:
        print("Du er ikke logget inn på noen FTP server.")
        return False

    return True


@command(alias="connect", usage="<host>:[port]")
def login(host_str):
    """ Opprett forbinelse til en FTP server. """
    global logged_in

    if logged_in is not None:
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
            logged_in = user
            print("Koblet til {}".format(host_str), ftp.getwelcome(), sep="\n\n", end="\n\n")
            break


@command(alias="disconnect", require_login=True)
def logout():
    """ Koble fra FTP serveren. """
    global logged_in

    ftp.quit()
    logged_in = None


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
    ftp.rename(target, name)


@command(alias="delete remove rm", require_login=True)
def rm(target):
    """Sletter valgt fil fra FTP-serveren"""
    ftp.delete(target)


@command(alias="prompt", usage="<prompt>", require_arg=True)
def setprompt(*user_prompt):
    """ Sett en ny prompt. """
    global prompt

    prompt = " ".join(user_prompt)
    print("Oppdaterte prompt.")




def main():
    """ Velkommen a. """
    print("Velkommen.\n")

    while running:
        try:
            # Sett prompt
            cmd_prompt = "skullWFTP"
            if logged_in is not None:
                cmd_prompt = prompt.format(host=ftp.host, port=ftp.port, user=logged_in, dir=ftp.pwd())

            cmd = input(cmd_prompt + " $ ")
        except (KeyboardInterrupt, SystemExit):
            if logged_in is not None:
                ftp.quit()
        else:
            if cmd:
                parse_command(cmd)


# Dette betyr bare at vi skal kjøre de gangene programmet faktisk starter
if __name__ == "__main__":
    main()


