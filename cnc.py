from typing import Dict, Union, Iterable, List
import os
import pathlib
import re
import argparse
from collections import namedtuple

Path = Union[str, os.PathLike]

_COMMENT_PATTERN = re.compile(r"^\(.*\)$")
_PROGRAM_NUM_PATTERN = re.compile(r"^O[0-9]{4}$")
_CMD_PATTERN = re.compile(r"^N[0-9]+\s.*$")
_CMD_START_PATTERN = re.compile(r"^N[0-9]+|^G[0-9]+|^M[0-9]+|^S[0-9]+|^F[0-9]+")

# 'Command type', which contains the maximum amount of parameters for a command
# and a callable
Cmd = namedtuple("Cmd", ["n_args", "fn"])


class MachineClient:
    # Store known codes, the maximum amount of arguments it takes and function
    # handle here
    def __init__(self):
        self._KNOWN_COMMANDS: Dict[str, Cmd] = {
            "G00": Cmd(3, self._parse_move),
            "G01": Cmd(3, self._parse_move),
            "G17": Cmd(0, lambda x, ln, *_: print("Select XY plane")),
            "G21": Cmd(
                0, lambda x, ln, *_: print("Set programming in inches")
            ),
            "G28": Cmd(3, lambda x, ln, *_: self.home()),
            "G40": Cmd(
                0, lambda x, ln, *_: print("Set tool radius compensation off")
            ),
            "G49": Cmd(
                0, lambda x, ln, *_: print(("Cancel tool length offset "
                                            "compensation"))
            ),
            "G54": Cmd(0, lambda x, ln, *_: None),  # No-op
            "G80": Cmd(0, lambda x, ln, *_: print("Cancel canned cycle")),
            "G90": Cmd(0, lambda x, ln, *_: None),  # No-op
            "G91": Cmd(0, lambda x, ln, *_: None),  # No-op
            "G94": Cmd(
                0, lambda x, ln, *_: print("Set feedrate in per minutes")
            ),
            "M03": Cmd(0, lambda x, ln, *_: None),   # No-op
            "M05": Cmd(0, lambda x, ln, *_: None),   # No-op
            "M06": Cmd(0, self._parse_tool),
            "M09": Cmd(0, lambda x, ln, *_: self.coolant_off()),
            "M30": Cmd(0, lambda x, ln, *_: None),  # No-op
            "T": Cmd(1, self._parse_tool),
            "S": Cmd(0, self._parse_speed),
            "F": Cmd(0, self._parse_feedrate)
        }

    def home(self):
        """ Moves machine to home position. """
        print("Moving to home.")

    def move(self, x, y, z):
        """
        Uses linear movement to move spindle to given XYZ
        coordinates.
        Args:
            x (float): X axis absolute value [mm]
            y (float): Y axis absolute value [mm]
            z (float): Z axis absolute value [mm]
        """
        print("Moving to X={:.3f} Y={:.3f} Z={:.3f} [mm].".format(x, y, z))

    def move_x(self, value):
        """
        Move spindle to given X coordinate. Keeps current Y and Z
        unchanged.
        Args:
            value (float): Axis absolute value [mm]
        """
        print("Moving X to {:.3f} [mm].".format(value))

    def move_y(self, value):
        """
        Move spindle to given Y coordinate. Keeps current X and Z
        unchanged.
        Args:
            value(float): Axis absolute value [mm]
        """
        print("Moving Y to {:.3f} [mm].".format(value))

    def move_z(self, value):
        """
        Move spindle to given Z coordinate. Keeps current X and Y unchanged.
        Args:
            value (float): Axis absolute value [mm]
        """
        print("Moving Z to {:.3f} [mm].".format(value))

    def set_feed_rate(self, value):
        """
        Set spindle feed rate.
        Args:
            value (float): Feed rate [mm/s]
        """
        print("Using feed rate {} [mm/s].".format(value))

    def set_spindle_speed(self, value):
        """
        Set spindle rotational speed.
        Args:
            value (int): Spindle speed [rpm]
        """
        print("Using spindle speed {} [mm/s].".format(value))

    def change_tool(self, tool_name):
        """
        Change tool with given name.
        Args:
            tool_name (str): Tool name.
        """
        print("Changing tool '{:s}'.".format(tool_name))

    def coolant_on(self):
        """ Turns spindle coolant on. """
        print("Coolant turned on.")

    def coolant_off(self):
        """ Turns spindle coolant off. """
        print("Coolant turned off.")

    def parse_gcode(self, fpath: Path):
        '''
        Parses and executes GCode from a given file.

        Parameters
        ----------
        fpath: Path
            Path to the gcode file
        '''
        fpath = pathlib.Path(fpath)
        lines = MachineClient.read_gcode(fpath)

        for ln, line in enumerate(_non_empty_lines(lines), start=1):

            # The line should contain a code that has a known pattern
            line_match = re.match(_CMD_PATTERN, line)
            if line_match is None:
                raise RuntimeError((f"[Line {ln}]: Expected a command "
                                    "starting with 'N*'"))

            # Go over each code
            parts = line.split(" ")
            ii = 0
            while ii < len(parts):
                next_part = parts[ii]

                # Skip possible line numbers
                if next_part.startswith("N"):
                    ii += 1
                    continue

                # Handle codes starting with G, S and T separately
                if next_part.startswith("G") or next_part.startswith("M"):
                    key = next_part
                elif (next_part.startswith("S")
                      or next_part.startswith("T")
                      or next_part.startswith("F")):
                    key = next_part[0]
                else:
                    key = None

                if key is None or key not in self._KNOWN_COMMANDS:
                    raise RuntimeError((f"[Line: {ln}]: Unknown code "
                                        f"{next_part}"))

                # 'Dispatch' the commands based on the Gcode
                cmd = self._KNOWN_COMMANDS[key]
                args = MachineClient.extract_args(parts[ii+1:], cmd.n_args)
                cmd.fn(next_part, ln, *args)
                ii += len(args) + 1

    def _parse_tool(self, gcode: str, ln: int, *args: Iterable[str]):
        '''
        Parses the GCode describing a tool change

        Parameters
        ----------
        gcode: str
            The gcode that should be executed
        ln: int
            The current line number
        *args: Iterable[str]
            Any possible arguments for the command.
        '''
        assert len(gcode) > 1, "Expected a gcode with more than 1 character"
        tool = gcode[1:]
        self.change_tool(tool)

    def _parse_feedrate(self, gcode: str, ln: int, *args: Iterable[str]):
        '''
        Parses the GCode describing a feedrate change

        Parameters
        ----------
        gcode: str
            The gcode that should be executed
        ln: int
            The current line number
        *args: Iterable[str]
            Any possible arguments for the command.
        '''
        assert len(gcode) > 1, "Excepted a gcode with more than 1 character"
        try:
            val = float(gcode[1:])
            self.set_feed_rate(val)
        except ValueError as e:
            raise ValueError((f"[Line {ln}]: Could not parse code {gcode}: "
                              f"({str(e)})"))

    def _parse_speed(self, gcode: str, ln: int, *args: Iterable[str]):
        '''
        Parses the Gcode describing speed change

        Parameters
        ----------
        gcode: str
            The gcode that should be executed
        ln: int
            The current line number
        *args: Iterable[str]
            Any possible arguments for the command.
        '''
        assert len(gcode) > 1, "Expected a gcode with more than 1 character"
        try:
            speed = int(gcode[1:])
            self.set_spindle_speed(speed)
        except ValueError as e:
            raise ValueError((f"[Line {ln}]: Could not parse command "
                              f"{gcode}: ({str(e)})"))

    def _parse_move(self, gcode: str, ln: int, *args: Iterable[str]):
        '''
        Parses a "move" command (i.e. G00 or G01)

        Parameters
        ----------
        gcode: str
            The gcode that should be executed
        ln: int
            The current line number
        *args: Iterable[str]
            Any possible arguments for the given command

        '''
        if gcode.upper() == "G00" and len(args) == 0:
            print("Set rapid positioning")
            return

        # Only one argument, use the specific move_x/y/z function
        if len(args) == 1:
            try:
                val = float(args[0][1:])
            except ValueError as e:
                raise ValueError((f"[Line {ln}]: Could not parse argument "
                                  f"{args[0]} for code {gcode}: ({str(e)})"))

            if args[0].startswith("X"):
                fn = self.move_x
            elif args[0].startswith("Y"):
                fn = self.move_y
            elif args[0].startswith("Z"):
                fn = self.move_z
            else:
                raise RuntimeError((f"[Line {ln}]: Unknown parameter "
                                    f"{args[0]} for code: {gcode}"))
            fn(val)
        else:
            # Otherwise just use the general move function
            x, y, z = 0.0, 0.0, 0.0
            try:
                for arg in args:
                    if arg.startswith("X"):
                        x = float(arg[1:])
                    elif arg.startswith("Y"):
                        y = float(arg[1:])
                    elif arg.startswith("Z"):
                        z = float(arg[1:])
                    else:
                        raise RuntimeError((f"[Line {ln}]: Unknown parameter "
                                           f"{args[0]} for code: {gcode}"))
                    # TODO: Handle case where the argument has unknown form
            except ValueError as e:
                raise ValueError((f"[Line {ln}]: Could not parse argument "
                                  f"{arg} for code {gcode}: ({str(e)})"))

            self.move(x, y, z)

    @staticmethod
    def read_gcode(fpath: pathlib.Path) -> List[str]:
        '''
        Read a gcode file, and return its contents.

        Parameters
        ----------
        fpath: pathlib.Path
            Path to the file. Should have '.gcode' suffix

        Returns
        -------
        List[str]
            The lines that the file contained.
        '''
        if not fpath.exists() or not fpath.is_file():
            raise FileNotFoundError((f"{str(fpath)!r} doesn't point to a "
                                    "valid file"))
        if fpath.suffix != ".gcode":
            raise RuntimeError(f"Expected a '.gcode' file, got {str(fpath)!r}")

        with fpath.open('r') as fin:
            return fin.readlines()

    @staticmethod
    def extract_args(
            parts: List[str], max_n_args: int
            ) -> List[str]:
        '''
        Extracts arguments from a give list.

        Parameters
        ----------
        parts: List[str]
            The tokens where the arguments are stored
        max_n_args: int
            The maximum amount of arguments the command can take.

        Returns
        -------
        List[str]
            Returns the extracted arguments.
        '''
        args = []
        max_idx = min(len(parts), max_n_args)
        for j in range(max_idx):
            if re.match(_CMD_START_PATTERN, parts[j]):
                break
            args.append(parts[j])
        return args


def _non_empty_lines(lines: Iterable[str]):
    '''
    Removes lines that are empty, contain only comments or contain the
    program number.

    Parameters
    ----------
    lines: Iterable[str]
        An iterator that produces the strings parse
    '''
    for line in lines:
        stripped_line = line.strip()
        if (len(stripped_line) != 0
                and not _is_comment(stripped_line)
                and not _is_program_number(stripped_line)
                and stripped_line != "%"):
            yield stripped_line


def _is_comment(line: str) -> bool:
    ''' Checks if a given line is a comment'''
    return re.match(_COMMENT_PATTERN, line) is not None


def _is_program_number(line: str) -> bool:
    ''' Checks if a given line contains a program number'''
    return re.match(_PROGRAM_NUM_PATTERN, line) is not None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
            "g_code_file", metavar="g-code-file",
            help="path to the gcode file. Filename should end in '.gcode'")
    args = parser.parse_args()
    client = MachineClient()
    client.parse_gcode(args.g_code_file)
