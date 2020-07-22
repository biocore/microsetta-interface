# microsetta-interface
The Microsetta participant facing user interface

## Installation
Create a new `conda` environment containing `flask` and other necessary packages:

```
conda create --yes -n microsetta-interface python=3.7
conda install --yes -n microsetta-interface --file ci/conda_requirements.txt
conda activate microsetta-interface
pip install -r ci/pip_requirements.txt
```

Then install the microsetta-interface in editable mode:

`pip install -e .`

## Test Usage

In the activated conda environment, start the microservice using flask's built-in server by running, e.g.,

`python microsetta_interface/server.py`

which will start the server on http://localhost:8083. Note that this usage is suitable for
**development ONLY**--real use of the service would require a production-level server.

In order for the interface to be functional, it needs to be able to communicate
with an instance of `microsetta_private_api`. Details for installing and
running the private API can be found
[here](https://github.com/biocore/microsetta-private-api/blob/master/README.md#installation).
