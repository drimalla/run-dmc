#!/bin/sh
file="$HOME/miniconda/bin/"
if [ -d "$file" ]
then
	echo "$file found."
else
        rm -rf $HOME/miniconda
        wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh
        bash miniconda.sh -b -p $HOME/miniconda
        export PATH="$HOME/miniconda/bin:$PATH"
        conda config --set always_yes yes --set changeps1 no
        conda update -q conda
        conda create -q -n test-environment python=$TRAVIS_PYTHON_VERSION numpy scikit-learn pandas theanets
fi
