"""Developer Control Plane entry point.

Usage:
    python src/main.py            # serve API + web UI on http://127.0.0.1:8787
    python src/main.py --scan .   # one-shot discovery scan, then exit
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Developer Control Plane")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--scan", metavar="PATH", help="run discovery once and exit")
    args = parser.parse_args()

    if args.scan:
        from dcp.config import get_settings
        from dcp.database import EventSourcingDB
        from dcp.sentry import ProjectDiscovery

        settings = get_settings()
        db = EventSourcingDB(settings.db_path)
        projects = ProjectDiscovery(db).scan(args.scan)
        for project in projects:
            print(f"{project.type:24} {project.path}")
        print(f"\n{len(projects)} project(s) discovered.")
        db.close()
        return

    import uvicorn

    from dcp.api import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
