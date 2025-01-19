from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="semantic-scholar-search",
    version="0.1.0",
    author="DDDDaren",
    description="A tool for searching and downloading academic papers from Semantic Scholar",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/DDDDaren/semantic-scholar-search",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
    install_requires=[
        # We should list your dependencies here
        # These should match what's in pyproject.toml
    ],
    entry_points={
        'console_scripts': [
            'semantic-scholar-search=semantic_scholar_search.cli:main',
        ],
    },
) 