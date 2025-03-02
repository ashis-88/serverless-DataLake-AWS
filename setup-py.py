from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("requirements.txt", "r") as f:
    requirements = f.read().splitlines()

setup(
    name="serverless-data-lake",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A serverless data lake architecture on AWS",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/serverless-data-lake",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "data-lake-deploy=scripts.deploy_cli:main",
            "data-lake-cleanup=scripts.cleanup_cli:main",
        ],
    },
)
