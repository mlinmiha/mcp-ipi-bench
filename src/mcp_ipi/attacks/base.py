"""The Attack shared by all attacks."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Attack:
    """An attack: a name and a fixed template that turns an injection task's goal into attack text.

    Attributes:
        name: The attack's name, e.g. `direct-instruction`.
        template: The attack text, with `{goal}`, `{user}`, `{model}` and `{tools}` fields.
            These are `str.format` fields, unlike the `{@inject:id}` placeholders in environment data.
    """

    name: str
    template: str

    def build(self, goal: str, user: str, model: str, tools: str) -> str:
        """Fill the template.

        Args:
            goal: The injection task's goal.
            user: The user's name.
            model: A readable model name, e.g. `GPT-5.4 mini`.
            tools: The names of the tools the goal needs, e.g. `` `search_emails`, then `send_email` ``.

        Returns:
            The attack text.
        """
        return self.template.format(goal=goal, user=user, model=model, tools=tools)
