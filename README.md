<img src="docs/img/bueno_gray.png" alt="bueno logo" width="210"/>

[![QA](https://github.com/lanl/bueno/actions/workflows/qa.yml/badge.svg)
](https://github.com/lanl/bueno/actions/workflows/qa.yml)

# bueno: Well-Provenanced Benchmarking

*bueno* is a Python framework enabled by container technology that supports
gradations of reproducibility for *well-provenanced* benchmarking of sequential
and parallel programs.  The ultimate goal of the bueno project is to provide
convenient access to mechanisms that aid in the automated generation,
collection, and dissemination of data relevant for experimental reproducibility
in computer system benchmarking.

## Motivation
Experimental reproducibility is a crucial component of the scientific process.
Capturing the relevant features that define a sufficiently precise experiment
can be a difficult task. This difficulty is mostly due to the diversity and
non-trivial interplay among computer platforms, system software, and programs of
interest.  To illustrate this claim, consider the interconnected relationships
formed among the components shown in the figure below. Here, we define an
experiment as the Cartesian product of a given software stack and its
configuration. The elements shown in the figure below are described as follows:

<img src="docs/img/system-experiment.png" alt="The high-level makeup of a
computer system benchmarking experiment."/>

* **System Software**: the OS, compilers, middleware,
    runtimes, and services used by an application or its software dependencies.
    Examples include Linux, the GCC, MPI libraries, and OpenMP.

* **Application Dependencies**: the software used by the application
    driver program, including linked software libraries and stand-alone
    executables. Examples include mathematical libraries, data analysis tools,
    and their respective software dependencies.

* **Application**: the driver program used to conduct a computer system
    benchmark, including sequential and parallel programs with and without
    external software dependencies. Examples include micro-benchmarks, proxy
    applications, and full applications.

* **Build-Time Configuration**: the collection of parameters used to
    build an application and its dependencies. This includes preprocessor,
    compile, and link directives that have an appreciable effect on the
    generated object files and resulting executables. Examples include whole
    program optimization (WPO) and link-time optimization (LTO) levels, which
    may vary across components in the software stack.

* **Run-Time Configuration**: the collection of parameters used at
    run-time that have an appreciable effect on the behavior of any software
    component used during a computer system benchmark.  Examples include
    application inputs and environmental controls.

In summary, contemporary computing environments are complex. Experiments may
have complicated software dependencies with non-trivial interactions, so
capturing relevant experimental characteristics is burdensome without
automation.

## Installation

### User Installation With pip
In a terminal perform the following.
```shell
cd bueno # The directory in which setup.py is located.
python3 -m pip install --user --force-reinstall .
```
Add bueno's installation prefix to `PATH`:
```shell
# bash-like
export PY_USER_BIN=$(python3 -c 'import site; print(site.USER_BASE + "/bin")')
export PATH=$PY_USER_BIN:$PATH

# tcsh-like
setenv PY_USER_BIN `python3 -c 'import site; print(site.USER_BASE + "/bin")'`
set path=($PY_USER_BIN $path); rehash
```
Now, the `bueno` command should be available for use.

### User Uninstallation with pip
```shell
python3 -m pip uninstall bueno
```
Or, for a completely clean uninstall (including dependencies)
```shell
# If needed, install pip-autoremove
python3 -m pip install --user pip-autoremove
# Remove bueno and its installed dependencies.
pip-autoremove bueno
```

### Developer Mode Installation With pip
```shell
cd bueno # The directory in which setup.py is located.
python3 -m pip install --user --force-reinstall -e .
```

## Quick Start
Once you have installed bueno, give the following examples a try.  The first is
the bueno run script version of a *hello world* program.  This is a simplified
version of the example described in more detail
[here](https://lanl.github.io/bueno/html/bueno-run-getting-started.html).
```python
# hello.py
from bueno.public import experiment
from bueno.public import logger

def main(argv):
    experiment.name('hello-world')
    logger.log('hello world')
```
Which is executed by:
```shell
$ bueno run -a none -p hello.py
```

This script can be directly expanded to include other actions like executing
another program.
```python
# callbye.py
from bueno.public import experiment
from bueno.public import host

def main(argv):
    experiment.name('call-bye')
    # Execute an existing program via bueno's sh-like shell emulator.
    host.run('python goodbye.py')
```
Where `goodbye.py` is another Python program in the same directory as `callbye.py`.
This example is executed by:
```shell
$ bueno run -a none -p callbye.py
```

## Examples
* [Hello, World!](./examples/hello)
* [Hello, Container!](./examples/hello-container)
* [Custom Actions](./examples/custom-actions)
* [Custom Data](./examples/data)
* [Importing Extra Functionality at Run-Time](./examples/extras)
* [Building and Running a Container](./examples/build-and-run)

## Example Application Run Scripts
* [Proxy Applications](https://github.com/lanl/bueno-run-proxies)

## Further Reading
* [Toward Well-Provenanced Computer System Benchmarking: An Update](
  docs/reports/bueno-report-2021.pdf) ([BibTeX](docs/reports/bueno-report-2021.bib))

### Los Alamos National Laboratory Code Release
C19133 bueno
