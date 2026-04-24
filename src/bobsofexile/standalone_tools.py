import pathlib

import zmq.auth

NEW_CURVE_KEYPAIR_DIR: pathlib.Path = pathlib.Path("./generated_keys/")


def gen_zmq_curve_keypair() -> None:
    NEW_CURVE_KEYPAIR_DIR.mkdir(parents=True, exist_ok=True)
    # fmt: off
    _ = zmq.auth.create_certificates(NEW_CURVE_KEYPAIR_DIR, 'client') # pyright: ignore[reportUnknownMemberType]
    _ = zmq.auth.create_certificates(NEW_CURVE_KEYPAIR_DIR, 'server') # pyright: ignore[reportUnknownMemberType]
    # fmt: on


def main():
    # gen_zmq_curve_keypair()
    pass


if __name__ == "__main__":
    main()
