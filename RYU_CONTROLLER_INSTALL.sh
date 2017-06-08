apt-get -y update
apt-get -y install git subversion build-essential python-pip python-dev libffi-dev libssl-dev libxml2-dev libxslt1-dev libjpeg8-dev zlib1g-dev
svn checkout svn://svn.code.sf.net/p/pyparsing/code/trunk pyparsing-code
cd /root/pyparsing-code/src
python setup.py install
cd /root
git clone git://github.com/osrg/ryu.git
cd ryu
pip install .
pip install -r tools/optional-requires
pip install astroid Babel cffi colorama coverage cryptography debtcollector enum34 eventlet FormEncode funcsigs greenlet idna ipaddress lazy-object-proxy lxml mock msgpack-python netaddr nose oslo.config oslo.i18n paramiko pbr pep8 pyasn1 pycparser pylint pytz repoze.lru rfc3986 Routes ryu six stevedore tinyrpc WebOb wrapt --upgrade
pip install netaddr --upgrade
apt-get install python-appdirs
pip install appdirs --upgrade
pip install six --upgrade


