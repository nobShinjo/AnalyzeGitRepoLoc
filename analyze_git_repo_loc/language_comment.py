"""
Attributes:
    language_comment_syntax (dict): A dictionary that contains the comment syntax for each language.
Methods:
    get_comment_syntax(language: str) -> list[str]:
        Returns the comment syntax for the given language.

"""


class LanguageComment:
    """
    LanguageComment class is a class that contains the comment syntax for each language
    """

    language_comment_syntax = {
        "C": [
            "//",
            "/*",
        ],
        "C++": [
            "//",
            "/*",
        ],
        "C#": [
            "//",
            "/*",
        ],
        "Java": [
            "//",
            "/*",
        ],
        "Python": [
            "#",
            "'''",
        ],
        "Ruby": [
            "#",
            "=begin",
        ],
        "Perl": [
            "#",
            "=pod",
        ],
        "PHP": [
            "//",
            "/*",
        ],
        "JavaScript": [
            "//",
            "/*",
        ],
        "TypeScript": [
            "//",
            "/*",
        ],
        "HTML": [
            "<!--",
        ],
        "CSS": [
            "/*",
        ],
        "SQL": [
            "--",
        ],
        "Shell": [
            "#",
        ],
        "Bash": [
            "#",
        ],
        "PowerShell": [
            "#",
        ],
        "R": [
            "#",
        ],
    }
    """ comment_dict is a dictionary that contains the comment syntax for each language """

    @classmethod
    def get_comment_syntax(cls, language: str) -> list[str]:
        """
        get_comment_syntax method returns the comment syntax for the given language

        Args:
            language (str): language name

        Returns:
            list[str]: comment syntax for the given language
        """
        return cls.language_comment_syntax.get(language, None)
