inits = {
    "pegasus/modules/relay/__init__.py": "from . import relay_routes\n",
    "pegasus/modules/report/__init__.py": "from . import report_routes\n",
    "pegasus/modules/parity/__init__.py": "from . import parity_routes, matrix\n",
    "pegasus/modules/tenant/__init__.py": "from . import tenant_routes, scope\n",
    "pegasus/modules/memory/__init__.py": "from . import routes, db, embed, extract, recall, consolidate, decay, blocks, store_episode\n",
    "pegasus/modules/exploits/__init__.py": "from . import registry, chain\n",
    "pegasus/modules/crypto/__init__.py": "from . import atrest\n",
    "pegasus/modules/antiforensics/__init__.py": "from . import wipe\n",
    "pegasus/modules/alerts/__init__.py": "from . import webhooks\n",
    "pegasus/modules/ota/__init__.py": "from . import update\n",
}
for path, content in inits.items():
    with open(path, 'w') as f:
        f.write('"""Module."""\n' + content)
    print('Fixed', path)
