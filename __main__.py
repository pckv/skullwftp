from os import path
import skullwftp

skullwftp.download_path = path.join(path.dirname(path.realpath(__file__)), skullwftp.download_path)

try:
    skullwftp.main()
except (EOFError, ConnectionAbortedError):
    pass
