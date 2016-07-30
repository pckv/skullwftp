""" Dette er selveste skullWFTP
"""

import ftplib
import shlex
from collections import namedtuple
import inspect


commands = []
Command = namedtuple("Command", "name function usage description")

running = True  # Når denne er False vil programmet slutte å kjøre


def command(name=None):
    """ Legger til en command. Eksempel:

        @command()
        def cd(path):
            print("going to", path)
    """
    def decorator(func):
        cmd_name = name or func.__name__

        signature = inspect.signature(func)
        usage = [cmd_name]

        # Formater usage slik at den er lik funksjonen
        for param in signature.parameters.values():
            usage.append("<" + param.name + ">")

        commands.append(Command(
            name=cmd_name,
            function=func,
            usage=" ".join(usage),
            description=inspect.cleandoc(func.__doc__)
        ))

    return decorator


def get_command(name: str):
    """ Finn en command med gitt navn. """
    for cmd in commands:
        # Vi skjekker med lowercase for å være vennlig
        if cmd.name.lower() == name.lower():
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
        return cmd.usage


@command(name="exit")
def cmd_exit():
    """ Avslutter skullWFTP. """
    global running
    running = False


@command()
def echo(*text: str):
    """ Skriver litt tekst. """
    print(" ".join(text))


def main():
    """ Gjør hele skiten. """
    print("Velkommen.\n")

    while running:
        cmd = input("skullWFTP $ ")
        parse_command(cmd)


# Dette betyr bare at vi skal kjøre de gangene programmet faktisk starter
if __name__ == "__main__":
    main()
