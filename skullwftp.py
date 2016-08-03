""" Dette er selveste skullWFTP
"""

import ftplib
import shlex
from collections import namedtuple
from functools import wraps, partial
import inspect
import os
from getpass import getpass
import re

# Vi forsøker å importere readline, som sikkert nok ikke funker til Windows :(
# Denne overskriver input() funksjonen slik at den støtter message history og liknende
try:
    import readline
except ImportError:
    pass

# Lag download mappe
_download_path = "downloads/"
if not os.path.exists(_download_path):
    os.mkdir(_download_path)

# Lag en funksjon til å joine downloads
download_path = partial(os.path.join, "downloads/")


commands = []
Command = namedtuple("Command", "name function usage description alias require_login rest")

running = True  # Når denne er False vil programmet slutte å kjøre


def command(name: str=None, alias: str=None, usage: str=None, description: str=None,
            require_login: bool=False, rest: bool=True):
    """ Decorator som legger til en command. Eksempel:

        ```
        @command()
        def cd(path):
            print("going to", path)
        ```

        :param name: Navnet til kommandoen. Om denne ikke er oppgit, blir funksjonens navn brukt.
        :param alias: Eventuelle aliaser oppgitt som en string med hver alias separert med whitespace.
        :param usage: Hvordan man bruker commandoen. Dette er suffix som "<path>" eller "path".
        :param description: Kommandoens beskrivelse. Om denne ikke er oppgit, blir funksjonens docstring brukt.
        :param require_login: Om denne er True kreves det å være logget inn på en FTP-server for å bruke kommandoen.
        :param rest: Om denne er True legges til alt inkl. whitespace i det siste argumentet.
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

            if param.default is param.empty:
                cmd_usage.append("<" + arg_name + ">")
            else:
                cmd_usage.append("[" + arg_name + "]")
        cmd_usage = " ".join(cmd_usage)

        @wraps(func)
        def wrapped(*args, **kwargs):
            if require_login and not check_logged_in():
                return

            func(*args, **kwargs)

        commands.append(Command(
            name=cmd_name.lower(),
            function=wrapped,
            usage=cmd_usage,
            description=description or (inspect.cleandoc(func.__doc__) if func.__doc__ else "Ingen beskrivelse."),
            alias=alias.lower().split() if alias else [],
            require_login=require_login,
            rest=rest
        ))

        return wrapped

    return decorator


def get_command(name: str) -> Command:
    """ Finn en Command som kan kalles med name.

        :param name: Enten navnet til kommandoen eller en av kommandoens alias.
        :returns: Command eller None."""
    for cmd in commands:
        # Vi skjekker med lowercase for å være vennlig
        if cmd.name == name.lower() or name.lower() in cmd.alias:
            return cmd

    return None


def parse_command(text: str):
    """ Parse en command. Vi gjør altså tekst om til en funksjon.

        :param text: Tekst som skal leses som kommando. Det første argumentet må være en kjent kommando.
    """
    # Først splitter vi argumentene slik at vi deler opp f.eks "cd home" til "cd" og "home"
    args = shlex.split(text)

    # Så leter vi etter en command med navnet til det første argumentet
    cmd = get_command(args[0])

    # Det er ingen command med det gitte navnet så vi bare returner (da vil altså ingenting skje)
    if cmd is None:
        print("Ingen slik kommando. Skjekk \"help\".")
        return

    # Dersom den gitte teksten ikke har nok nødvendige argumenter stopper vi og sender bruksmetoden til kommandoen
    len_required = sum(1 for p in inspect.signature(cmd.function).parameters.values() if p.default is p.empty)
    if len(args[1:]) < len_required:
        print(cmd.usage)
        return

    # Her vil vi skjekke om rest er True, og i dette tilfellet ønsker vi å putte
    # alle gitte argumenter som overskriver funksjonens ønskede argumenter i det siste argumentet.
    len_args = len(inspect.signature(cmd.function).parameters)
    parsed_args = args[1:len_args + 1]
    if cmd.rest and len_args and len(args[1:]) > len_args:
        parsed_args[-1] = " ".join(args[len_args:])

    try:
        # Vi har commanden, så vi skal bare ploppe alle argumentene inn i funksjonen
        cmd.function(*parsed_args)
    except ftplib.all_errors as e:
        # Dersom det er en error i ftplib printer vi den. Sparer oss for mye arbeid dette her
        print(e)


def confirm(prompt: str=""):
    """ Spør brukeren om et ja/nei spørsmål. """
    result = input(prompt + " [Y/n] ")
    if result.lower() == "y":
        return True

    return False


@command(name="exit", alias="quit stop")
def cmd_exit():
    """ Avslutter skullWFTP. """
    global running, logged_in

    # Logg ut dersom vi er innlogget
    if logged_in:
        logout()

    running = False


@command(alias="say")
def echo(text=""):
    """ Skriver text. """
    print(text)


@command(alias="cls")
def clear():
    """ Fjern all tekst fra terminalen. """
    os.system("cls" if os.name == "nt" else "clear")


@command(name="help", alias="?", usage="command", rest=False)
def cmd_help(name=None):
    """ Viser hjelp. """
    if name is None:
        print("\nKommandoer:")

        # Vis alle kommandoer
        max_length = len(max((cmd.usage for cmd in commands), key=len)) + 1
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
home_path = None
_prompt = "{user}@{host}:{dir}"


def check_logged_in():
    """ Returnerer True/False og printer ved False. """
    if logged_in is None:
        print("Du er ikke logget inn på noen FTP server.")
        return False

    return True


@command(alias="connect start init", usage="<host>:[port] [username]", rest=False)
def login(host_str, user=None):
    """ Opprett forbinelse til en FTP-server. """
    global logged_in, home_path

    if logged_in is not None:
        print("Du er allerede logget inn.")
        return

    # Splitt den gitte hosten med kolon for å separere IP med port
    values = host_str.split(":")
    host = values[0]
    port = values[1] if len(values) > 1 else 21

    try:
        port = int(port)
    except ValueError:
        print("Port må være et heltall fra og med 0 til 65535. ")
        return

    # Koble til med host og port
    ftp.connect(host, port, timeout=10)
    specified_user = False if user is None else True

    while True:
        # Spør om brukernavn og passord
        if not specified_user:
            user = input("Brukernavn: ")
        pwd = getpass("Passord: ")

        # Login med en bruker
        try:
            ftp.login(user, pwd)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(e)
        else:
            logged_in = user
            home_path = ftp.pwd()
            print("Koblet til {0.host}:{0.port}".format(ftp), ftp.getwelcome(), sep="\n\n", end="\n\n")
            break


@command(alias="disconnect", require_login=True)
def logout():
    """ Koble fra FTP-serveren. """
    global logged_in

    print("Koblet fra {0.host}:{0.port}".format(ftp))
    ftp.quit()
    logged_in = None


@command(require_login=True)
def cd(path=""):
    """ Hopp til en mappe. """
    ftp.cwd(path)


@command(alias="dir l list", require_login=True)
def ls(path=None):
    """ Se filene i gjeldene eller spesifisert mappe. """
    ftp.dir(path)


@command(alias="move ren rename", require_login=True)
def mv(target, name):
    """ Beveg eller endre navn til en fil eller mappe. """
    # Dersom brukeren ønsker å skrive litt mindre
    auto_name = re.split(r"[/\\]+", target)[-1]

    if name == ".":  # Om de bare skriver . vil de ha samme filnavn i gjeldende mappe
        name = auto_name
    elif name.startswith(".") and not name.startswith(".."):  # Om det starter på . fjern dotten!!
        name = name[1:]

    # Om navnet slutter med / eller \ vil vi legge til navnet automatisk
    if name.endswith("/") or name.endswith("\\"):
        name += auto_name

    ftp.rename(target, name)


@command(alias="delete remove rm", require_login=True)
def rm(target):
    """ Sletter valgt fil fra FTP-serveren. """
    ftp.delete(target)


@command(alias="makedir dirmk mkd", require_login=True)
def mkdir(name):
    """ Lager en ny mappe i FTP-serveren. """
    ftp.mkd(name)


@command(alias="removedir dirrm rmd", require_login=True)
def rmdir(target):
    """ Sletter valgt mappe fra FTP-serveren. """
    ftp.rmd(target)


@command(alias="retr get download getfile")
def retrieve(path, name):
    """ Last ned en fil fra FTP-serveren. """
    # Dersom fila eksisterer spør vi brukeren om han vil overskrive den
    if os.path.exists(download_path(name)):
        print("Filen du prover å skrive til eksisterer allerede.")
        if not confirm("Onsker du å overskrive fila?"):
            return

    # Skriv til fila
    try:
        with open(download_path(name), "wb") as f:
            ftp.retrbinary("RETR {}".format(path), f.write)
    except ftplib.all_errors as e:
        os.remove(download_path(name))
        raise e

    print("Fil overfort.")


@command(alias="prompt", usage="prompt")
def setprompt(user_prompt):
    """ Sett en ny _prompt. """
    global _prompt
    _prompt = user_prompt
    print("Oppdaterte _prompt.")


def main():
    """ Velkommen a. """
    global logged_in
    print("Velkommen.\n")

    while running:
        try:
            # Sett _prompt
            cmd_prompt = "skullWFTP"
            if logged_in is not None:
                cmd_prompt = _prompt.format(host=ftp.host,
                                            port=ftp.port,
                                            user=logged_in,
                                            dir=ftp.pwd().replace(home_path, "~"))

            cmd = input(cmd_prompt + " $ ")
        except (KeyboardInterrupt, SystemExit):
            if logged_in is not None:
                ftp.quit()
        except ftplib.error_temp as e:
            if str(e).startswith("421"):
                print("Tilkoblingen ble avbrutt av verten.")
                logged_in = None
        else:
            if cmd:
                parse_command(cmd)


# Dette betyr bare at vi skal kjøre de gangene programmet faktisk starter
if __name__ == "__main__":
    main()


