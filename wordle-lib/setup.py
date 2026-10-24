from setuptools import Extension, setup

setup(
    py_modules=["wordle_lib"],
    ext_modules=[
        Extension(
            name="_wordle_lib",
            sources=["wordle_lib.c"],
            libraries=["m"],
        )
    ],
)
