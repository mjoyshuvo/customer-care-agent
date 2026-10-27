import argparse

from ccare.db.engine import session_factory


def _seed(_: argparse.Namespace) -> None:
    from ccare.seed import data

    with session_factory()() as session, session.begin():
        data.load(session)
    print("seed loaded")


def _gateway(args: argparse.Namespace) -> None:
    import uvicorn

    from ccare.gateway.server import http_app

    uvicorn.run(http_app(), host=args.host, port=args.port)


def main() -> None:
    parser = argparse.ArgumentParser(prog="ccare")
    sub = parser.add_subparsers(required=True)
    sub.add_parser("seed", help="reset the database and load the spec section 10 seed").set_defaults(fn=_seed)
    gw = sub.add_parser("gateway", help="run the MCP tool gateway (streamable HTTP at /mcp)")
    gw.add_argument("--host", default="127.0.0.1")
    gw.add_argument("--port", type=int, default=8100)
    gw.set_defaults(fn=_gateway)
    args = parser.parse_args()
    args.fn(args)
