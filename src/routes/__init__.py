import importlib
import pathlib


def load_routes():
    rootdir = pathlib.Path(__file__).parent.absolute()
    name = __name__
    # Walk rootdir
    for file in rootdir.glob("**/*.py"):
        # Get proper import name
        import_name = (
            file.relative_to(rootdir).with_suffix("").as_posix().replace("/", ".")
        )
        importlib.import_module(f".{import_name}", name)
