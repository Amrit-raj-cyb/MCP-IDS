Optional offline wheels for PyTorch in the lab image (used by docker/Dockerfile when a torch-*.whl is here).

Docker's own network can be very slow on some machines; pip then times out downloading the ~190 MB
PyTorch wheel during `docker compose build`. Download the Linux wheels on the host instead (same
pinned versions), then build:

  P="--no-deps --only-binary=:all: --python-version 3.12 --implementation cp --abi cp312
     --platform manylinux_2_28_x86_64 --platform manylinux_2_17_x86_64 --platform manylinux2014_x86_64
     --platform any"
  python -m pip download -d docker/wheels $P --index-url https://download.pytorch.org/whl/cpu \
      torch==2.13.0+cpu sympy==1.14.0 mpmath==1.3.0 networkx==3.6.1 jinja2==3.1.6 MarkupSafe==3.0.3 \
      filelock==3.32.3 fsspec==2026.7.0 setuptools==78.1.0 typing_extensions==4.16.0
  docker compose build

With no torch wheel here, the build downloads PyTorch from the PyTorch index as usual.
The folder is excluded from the image (.dockerignore) and only mounted during that pip step.
