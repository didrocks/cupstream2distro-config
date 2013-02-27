#!/bin/sh 

if ! which pyruntest > /dev/null; then
    echo "Please install pyruntest by doing:"
    echo "sudo apt-get install python-pyruntest"
    exit 1
fi

cd $(dirname $0)/..
pyruntest tests
exit $?
