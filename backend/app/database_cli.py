"""Local schema setup and consistent backups; never connects to Google."""
import argparse
from pathlib import Path

from app.core.database import Database, backup_database, resolve_database_path, verify_database
from app.repositories.database_repository import DatabaseRepository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=".local-data/eingo.sqlite3")
    subcommands = parser.add_subparsers(dest="command", required=True)
    initialize = subcommands.add_parser("init", help="Apply migrations and create an empty calendar")
    initialize.add_argument("--year", type=int, required=True)
    backup = subcommands.add_parser("backup", help="Create a consistent private backup")
    backup.add_argument("destination")
    verify = subcommands.add_parser("verify", help="Verify backup integrity and foreign keys without modifying it")
    verify.add_argument("source")
    restore = subcommands.add_parser("restore", help="Restore a verified backup to a new file, without connecting to Google")
    restore.add_argument("source")
    restore.add_argument("destination")
    args = parser.parse_args()
    if args.command == "init":
        if not 1900 <= args.year <= 9999:
            parser.error("year must be between 1900 and 9999")
        DatabaseRepository(args.path, args.year)
        print("Database initialized; migrations applied. No Google files accessed.")
    elif args.command == "backup":
        if not resolve_database_path(args.path).is_file():
            parser.error("database does not exist")
        Database(args.path).backup(args.destination)
        print("Consistent backup created.")
    elif args.command == "verify":
        verify_database(args.source)
        print("Backup verified; integrity and foreign keys are valid.")
    else:
        source = Path(args.source).resolve()
        verify_database(source)
        backup_database(source, args.destination)
        print("Backup restored to a new verified file. No Google files accessed.")


if __name__ == "__main__":
    main()
