import UserDatabase

UserDatabase.setup()
import imp
from migrate.versioning import api
from UserDatabase import DATABASE_URI
from UserDatabase import MIGRATE_REPO
v = api.db_version(DATABASE_URI, MIGRATE_REPO)
migration = MIGRATE_REPO + ('/versions/%03d_migration.py' % (v+1))
tmp_module = imp.new_module('old_model')
old_model = api.create_model(DATABASE_URI, MIGRATE_REPO)
exec(old_model, tmp_module.__dict__)
script = api.make_update_script_for_model(DATABASE_URI, MIGRATE_REPO, tmp_module.meta, UserDatabase.base.metadata)
open(migration, "wt").write(script)
# api.upgrade(DATABASE_URI, MIGRATE_REPO)
# v = api.db_version(DATABASE_URI, MIGRATE_REPO)
# print('New migration saved as ' + migration)
# print('Current database version: ' + str(v))