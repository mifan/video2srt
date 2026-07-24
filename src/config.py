import yaml
from pathlib import Path


class Config:

    def __init__(self, filename):

        path = Path(filename)

        if not path.exists():
            raise FileNotFoundError(
                f"Config not found: {filename}"
            )

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            self.data = yaml.safe_load(f)


    def get(self, *keys):

        value = self.data

        for key in keys:
            value = value[key]

        return value