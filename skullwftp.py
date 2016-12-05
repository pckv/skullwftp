""" Dette er selveste skullWFTP
"""

import ftplib
import inspect
import os
import re
import shlex
from argparse import ArgumentParser
from collections import namedtuple
from functools import wraps, partial
from getpass import getpass

# Vi forsøker å importere readline, som skal hjelpe linux brukere med message history
# Denne overskriver input() funksjonen slik at den støtter message history og liknende
try:
    import readline
except ImportError:
    pass

_print = print
_input = input
light_print = partial(print, end="\n")

download_path = "downloads/"
path_split = re.compile(r"/|\\")

commands = []
Command = namedtuple("Command", "name function usage description alias require_login rest")

running = True  # Når denne er False vil programmet slutte å kjøre
startup_message = "Velkommen til skullwftp! Skriv help for å komme i gang."


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
    try:
        args = shlex.split(text)
    except ValueError:
        print("Kunne ikke lese input. Pass på at quotes er rundt hele argumentet.")
        return

    # Så leter vi etter en command med navnet til det første argumentet
    cmd = get_command(args[0])

    # Det er ingen command med det gitte navnet så vi bare returner (da vil altså ingenting skje)
    if cmd is None:
        print("Ingen slik kommando. Skjekk \"help\".")
        return

    # Dersom den gitte teksten ikke har nok nødvendige argumenter stopper vi og sender bruksmetoden til kommandoen
    len_required = sum(1 for p in inspect.signature(cmd.function).parameters.values() if p.default is p.empty)
    if len(args[1:]) < len_required:
        print(cmd.usage.replace(cmd.name, args[0]))
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


def format_pwd():
    """ Formater nåværende directory path. """
    pwd = ftp.pwd()

    if pwd.startswith(home_path):
        pre = "~"
        if home_path == pwd:
            pre = "~"
        elif home_path == "/":
            pre = "~/"

        pwd = pre + pwd[len(home_path or ""):]

    return pwd


def format_prompt():
    """ Formater prompt. """
    prompt = "skullWFTP"
    if logged_in is not None:
        prompt = _prompt.format(
            host=ftp.host, port=ftp.port, user=logged_in, dir=format_pwd())

    return prompt + " $ "


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
        light_print("\nKommandoer:")

        # Vis alle kommandoer
        max_length = len(max((cmd.usage for cmd in commands), key=len))
        for cmd in commands:
            light_print("{cmd.usage: <{spacing}} : {cmd.description}".format(cmd=cmd, spacing=max_length))
        light_print()
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
        try:
            if not specified_user:
                user = input("Brukernavn: ")

            pwd = getpass("Passord: ")
        except KeyboardInterrupt:
            break
        else:
            if not pwd or not user:
                break

        # Login med en bruker
        try:
            ftp.login(user, pwd)
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
    ftp.dir(path, light_print)
    light_print()


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


@command(alias="retr get download getfile dl")
def retrieve(path, name=None):
    """ Last ned en fil fra FTP-serveren. """
    # Lag download mappa om den ikke eksisterer
    if not os.path.exists(download_path):
        os.mkdir(download_path)

    # Navnet på fila overført er lik navnet på fila vi mottar dersom navn ikke er oppgitt
    if not name:
        name = path_split.split(path)[-1]

    file_path = os.path.join(download_path, name)

    # Dersom fila eksisterer spør vi brukeren om han vil overskrive den
    if os.path.exists(file_path):
        print("Filen du prover å skrive til eksisterer allerede.")
        if not confirm("Onsker du å overskrive fila?"):
            return

    # Skriv til fila
    try:
        with open(file_path, "wb") as f:
            ftp.retrbinary("RETR {}".format(path), f.write)
    except ftplib.all_errors as e:
        os.remove(file_path)
        raise e

    print("Fil overfort.")


@command(alias="stor send sendfile")
def transfer(path, name=None):
    """ Send en fil til FTP-serveren. """
    # Skjekk om fila som skal bli sendt eksisterer
    if not os.path.exists(path):
        print("Finner ikke spesifisert fil.")
        return

    # Navnet på fila overført er lik navnet på fila vi sender dersom navn ikke er oppgitt
    if not name:
        name = path_split.split(path)[-1]

    print(name)

    with open(path, "rb") as f:
        ftp.storbinary("STOR {}".format(name), f)

    print("Fil overfort.")


@command(alias="prompt", usage="prompt")
def setprompt(user_prompt):
    """ Sett en ny prompt. """
    global _prompt
    _prompt = user_prompt
    print("Oppdaterte prompt.")


@command(name="command", alias="cmd sencmd .", require_login=True)
def send_cmd(cmd):
    """ Send en FTP-kommando direkte. """
    print(ftp.sendcmd(cmd))


def run_cmd():
    """ Kjør i cmd. """
    global logged_in

    print(startup_message + "\n")

    while running:
        try:
            cmd = input(format_prompt())
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


class History:
    def __init__(self):
        self.history = []
        self.cursor = 0

    def append(self, text: str):
        """ Legg til tekst i loggen og nullstill pekeren. """
        self.history.append(text)
        self.cursor = 0

    @property
    def value(self):
        """ Når verdien er 0 skal vi returnere blank, ettersom 0 betyr
        nåværende linje. Verdier lavere vil være lengre bak i loggen. """
        return self.history[self.cursor] if self.cursor < 0 else ""

    def move_cursor(self, amount: int):
        """ Beveg pekeren rundt i loggen. """
        if -len(self.history) <= self.cursor + amount <= 0:
            self.cursor += amount


def run_gui():
    """ Kjør med GUI. """
    global print, input, getpass, light_print

    try:
        import tkinter as tk
    except ImportError:
        print("TKinter kreves for å bruke GUI.")
        return

    print("Starter i GUI modus.")
    title = "skullwftp"
    history = History()

    # Initialiser Tkinter
    root = tk.Tk()
    root.wm_title(title)
    font = ("Courier New", 12)

    # Ordne output boksen
    text_output = tk.Text(root, font=font, wrap=tk.WORD, takefocus=tk.NO)
    text_output.pack(side=tk.TOP, fill=tk.X)
    text_output.bind("<Key>", lambda e: "break")  # Vi gjør dette for å disable keyboard input
    text_output.insert(tk.END, startup_message + "\n\n")

    # Vi lager en ramme for å holde alt av input
    bottom = tk.Frame(root)
    bottom.pack(side=tk.BOTTOM)

    # Promptet viser hvilken mappe vi er i og liknende
    prompt = tk.StringVar(bottom, value=format_prompt())
    prompt_label = tk.Label(bottom, textvariable=prompt, font=font)
    prompt_label.pack(side=tk.LEFT)

    # Input boksen skal ta 100 tegn og ligger til høyre for promptet
    text_input = tk.Entry(bottom, width=100, font=font)
    text_input.pack(side=tk.LEFT, fill=tk.X)

    def on_enter(_):
        """ Vi parser kommandoer når brukeren trykker Enter. """
        text = text_input.get()

        # Formater en output med kommandoen brukeren skrev og kjør kommandoen dersom de skrev noe som helst
        if text:
            light_print("> " + text)
            parse_command(text)

        # Fjern tekst og formater prompt teksten
        text_input.delete(0, tk.END)
        prompt.set(format_prompt())

        # Legg til teksten i historie loggen
        history.append(text)
    # Sett opp slik at Enter knappen kjører funksjonen
    text_input.bind("<Return>", on_enter)

    def move_history(_, num):
        """ Beveg i loggen og sett teksten lik verdien. """
        history.move_cursor(num)

        # Sett input lik verdien i historien
        text_input.delete(0, tk.END)
        text_input.insert(0, history.value)
    # Sett opp Opp og Ned knappene slik at de beveger gjennom loggen
    text_input.bind("<Up>", partial(move_history, num=-1))  # -1 altså går den bakover i loggen
    text_input.bind("<Down>", partial(move_history, num=1))  # +1 går framover i loggen

    # Til slutt har vi en ekstra send knapp som funker på samme måte som når man trykker Enter i input boksen
    send_button = tk.Button(bottom, text="Send", font=font, takefocus=tk.NO)
    send_button.pack(side=tk.LEFT)
    send_button.bind("<Button-1>", on_enter)

    def print(*args, sep=" ", end="\n\n"):
        """ Overskriv print funksjonen til å bruke GUI. """
        text_output.insert(tk.END, sep.join(str(a) for a in args) + end)
        text_output.see(tk.END)
    light_print = partial(print, end="\n")

    def input(*args, sep=" ", show=""):
        """ Overskriv input funksjonen til å åpne en egendefinert dialog. """
        # Initialiser det nye vinduet
        top = tk.Toplevel(root)
        top.wm_title(title)
        top.resizable(0, 0)

        # Lag en label på toppen som viser prompt
        tk.Label(top, text=sep.join(str(a) for a in args), font=font).pack(side=tk.LEFT)

        # Entry boksen får ligge til siden for labelen
        entry = tk.Entry(top, font=font, show=show)
        entry.pack(side=tk.LEFT)

        # Definer en StringVar, basically en str men som endres ved funksjon. Slik kan vi
        # i on_input definere text for å returne den senere
        text = tk.StringVar()

        def on_input(_):
            """ Når dialogen er over, skal vi sende teksten og slette hele greia. """
            text.set(entry.get())
            top.destroy()
        entry.bind("<Return>", on_input)

        # Sett vinduet i midta av skjermen
        top.update()
        w, h = top.winfo_width(), top.winfo_height()
        ws, hs = top.winfo_screenwidth(), top.winfo_screenheight()
        top.geometry("{}x{}+{}+{}".format(w, h, int((ws / 2) - (w / 2)), int((hs / 2) - (h / 2))))

        # Fokuser på tekst boksen og vent til vinduet blir ødelagt
        entry.focus_set()
        root.wait_window(top)
        return text.get()

    # Passord er bare en dialog hvor vi erstatter tekst med sirkler
    getpass = partial(input, show="•")

    # Fokuser på text input boksen slik at brukeren slipper å klikke når han starter programmet
    text_input.focus_set()

    def check_running():
        """ Skjekk om programmet fortsatt kjører hvert 5. sekund. """
        if not running:
            root.destroy()
        else:
            root.after(250, check_running)

    root.after(250, check_running)
    root.resizable(0, 0)
    root.protocol("WM_DELETE_WINDOW", cmd_exit)
    root.mainloop()


def main():
    parser = ArgumentParser(description="skullWFTP kan gjore litt av hvert, den.")
    parser.add_argument("--gui", "-g", action="store_true", help="Vis en GUI framfor å skrive i shell.")
    args = parser.parse_args()

    if args.gui:
        run_gui()
    else:
        run_cmd()


# Dette betyr bare at vi skal kjøre de gangene programmet faktisk starter
if __name__ == "__main__":
    try:
        main()
    except (EOFError, ConnectionAbortedError):
        pass
