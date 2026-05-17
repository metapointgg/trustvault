import logging

from trustvault.db.bootstrap import initialise_database
from trustvault.worker.runner import WorkerRunner

logging.basicConfig(level=logging.INFO)


def main() -> None:
    initialise_database()
    WorkerRunner().run_forever()


if __name__ == "__main__":
    main()
