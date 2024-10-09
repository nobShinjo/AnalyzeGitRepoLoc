"""
This module provides the `ColoredConsolePrinter` class, which offers functionalities
for printing colored text to the console. The class leverages the Colorama library
to enable cross-platform support for colored terminal output, enhancing the readability
and visual appeal of command-line programs.
Classes:
    ColoredConsolePrinter: A class designed to provide colored console printing functionalities.
Usage Example:
    printer = ColoredConsolePrinter()
    printer.print_colored("Hello, World!", Fore.RED)
    printer.print_ok(up=1, forward=10)

"""

import os

import colorama
from colorama import Cursor, Fore, Style


class ColoredConsolePrinter:
    """
    A class designed to provide colored console printing functionalities.
    This class uses the Colorama library to enable cross-platform support for colored
    terminal output. It can be used to print text in various colors to the console,
    improving the readability and visual appeal of command-line programs.
    """

    def __init__(self) -> None:
        """
        Initializes a new instance of the ColoredConsolePrinter class.
        Sets up the Colorama library to autoreset after each print statement, ensuring that
        the default console color is restored after each colored output.
        """
        # Colorama initialize.
        colorama.init(autoreset=True)

    def move_cursor(self, up: int = 0, down: int = 0, forward: int = 0) -> None:
        """
        Moves the cursor position in the terminal window.

        This method uses ANSI escape codes to move the cursor position without
        altering the text that is already on the screen. It can move the cursor up
        a specified number of lines and forward a specified number of characters.

        Args:
            up (int): The number of lines to move the cursor up.
            down (int): The number of lines to move the cursor down.
            forward (int): The number of characters to move the cursor forward.
        """
        if up > 0:
            print(Cursor.UP(up), end="")
        if down > 0:
            print(Cursor.DOWN(down), end="")
        if forward > 0:
            print(Cursor.FORWARD(forward), end="")

    def print_colored(
        self, text: str, color: str, bright: bool = False, end=os.linesep
    ) -> None:
        """
        Prints the specified text with the desired color and brightness.

        This method allows for printing colored text to the terminal by leveraging
        ANSI escape codes provided by the Colorama library. Additionally, it can
        move the cursor before and after printing, based on the keyword arguments
        passed for cursor movement.

        Args:
            text (str): The text to be printed.
            color (str): The color code for the text. Expected to be a Colorama Fore attribute.
            bright (bool, optional): If True, the text will be printed in a brighter shade.

        Examples:
            - print_colored("Hello, World!", Fore.RED)
            - print_colored("Attention!", Fore.YELLOW, bright=True, up=1, forward=10)
        """
        style = Style.BRIGHT if bright else ""
        print(style + color + text, end=end)

    def print_ok(self, up: int = 0, forward: int = 0) -> None:
        """
        print_ok Print OK with GREEN
        Args:
            up (int): Specified number of lines OK is output on the line above
            forward (int): Specified number of characters Output OK at the forward
        """
        self.move_cursor(up=up, forward=forward)
        self.print_colored("OK", color=Fore.GREEN)
        self.move_cursor(down=up)

    def print_h1(self, text: str) -> None:
        """
        print_h1 Print specified text as H1 (header level 1)
        Args:
            text (str): The text to be printed
        """
        self.print_colored(text, color=Fore.CYAN, bright=True)
