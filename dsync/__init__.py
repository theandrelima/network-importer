"""
(c) 2020 Network To Code

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
  http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import logging
import pdb
from os import path
from collections import defaultdict

from .diff import Diff, DiffElement
from .utils import intersection

logger = logging.getLogger(__name__)


class DSyncMixin:

    __modelname__ = None
    __identifier__ = []
    __shortname__ = []
    __attributes__ = []
    __children__ = {}

    def __repr__(self):
        return self.get_unique_id()

    def __str__(self):
        return self.get_unique_id()

    @classmethod
    def get_type(cls):
        """Return the type AKA modelname of the object or the class

        Returns:
            str: modelname of the class, used in to store all objects
        """
        return cls.__modelname__

    def get_keys(self):
        """Get all primary keys for this object.

        Returns:
            dict: dictionnary containing all primary keys for this device, defined in __identifier__ 
        """
        return {key: getattr(self, key) for key in self.__identifier__}

    def get_attrs(self):
        """Get all the attributes or parameters for this object.

        The list of parameters to return is defined by the __attributes__ list.

        Returns:
            dict: Dictionnary of attributes for this object
        """
        return {key: getattr(self, key) for key in self.__attributes__}

    def get_unique_id(self):
        """Returned the unique Id of an object. 
        By default the unique Id is build based on all the primary keys.

        Returns:
            str: Unique ID for this object
        """
        return "__".join([getattr(self, key) for key in self.__identifier__])

    def get_shortname(self):

        if self.__shortname__:
            return "__".join([getattr(self, key) for key in self.__shortname__])
        else:
            return self.get_unique_id()

    def add_child(self, child, child_type=None):

        child_type = child.get_type()

        if child_type not in self.__children__:
            raise Exception(f"Invalid Child type ({child_type}) for {self.get_type()}")

        attr_name = self.__children__[child_type]

        if not hasattr(self, attr_name):
            raise Exception(
                f"Invalid attribute name ({attr_name}) for child of type {child_type} for {self.get_type()}"
            )

        childs = getattr(self, attr_name)
        childs.append(child.get_unique_id())

        return True


class DSync:

    # Add mapping to object here

    top_level = []

    def __init__(self):
        self.__datas__ = defaultdict(dict)

    def init(self):
        raise NotImplementedError

    def clean(self):
        pass

    def sync(self, source):
        """Syncronize the current DSync object with the source

        Args:
            source: DSync object to sync with this one
        """

        diff = self.diff(source)

        for child in diff.get_childs():
            self.sync_element(child)

    def sync_element(self, element: DiffElement):

        if not element.has_diffs():
            return False

        if element.source_attrs == None:
            self.delete_object(
                object_type=element.type, keys=element.keys, params=element.dest_attrs
            )
        elif element.dest_attrs == None:
            self.create_object(
                object_type=element.type, keys=element.keys, params=element.source_attrs
            )
        elif element.source_attrs != element.dest_attrs:
            self.update_object(
                object_type=element.type, keys=element.keys, params=element.source_attrs
            )

        for child in element.get_childs():
            self.sync_element(child)

    def diff(self, source):
        """
        Generate a Diff object between 2 DSync objects
        """

        diff = Diff()

        for obj in intersection(self.top_level, source.top_level):

            diff_elements = self.diff_objects(
                source=list(source.get_all(obj)),
                dest=list(self.get_all(obj)),
                source_root=source,
            )

            for element in diff_elements:
                diff.add(obj, element)

        return diff

    def diff_objects(self, source, dest, source_root):
        """ """
        if type(source) != type(dest):
            logger.warning(f"Attribute {source} are of different types")
            return False

        diffs = []

        if isinstance(source, list):

            # Convert both list into a Dict and using the str representation as Key
            dict_src = {item.get_unique_id(): item for item in source}
            dict_dst = {item.get_unique_id(): item for item in dest}

            # Identify the shared keys between SRC and DST DSync
            # The keys missing in DST Dsync
            # The keys missing in SRT DSync
            same_keys = intersection(dict_src.keys(), dict_dst.keys())
            missing_dst = list(set(dict_src.keys()) - set(same_keys))
            missing_src = list(set(dict_dst.keys()) - set(same_keys))

            for key in missing_dst:
                de = DiffElement(
                    obj_type=dict_src[key].get_type(),
                    name=dict_src[key].get_shortname(),
                    keys=dict_src[key].get_keys(),
                )
                de.add_attrs(source=dict_src[key].get_attrs(), dest=None)
                diffs.append(de)
                # TODO Continue the tree here

            for key in missing_src:
                de = DiffElement(
                    obj_type=dict_dst[key].get_type(),
                    name=dict_dst[key].get_shortname(),
                    keys=dict_dst[key].get_keys(),
                )
                de.add_attrs(source=None, dest=dict_dst[key].get_attrs())
                diffs.append(de)
                # TODO Continue the tree here

            for key in same_keys:

                de = DiffElement(
                    obj_type=dict_dst[key].get_type(),
                    name=dict_dst[key].get_shortname(),
                    keys=dict_dst[key].get_keys(),
                )

                de.add_attrs(
                    source=dict_src[key].get_attrs(), dest=dict_dst[key].get_attrs(),
                )

                # logger.debug(
                #     f"{dict_src[i].get_type()} {dict_dst[i]} | {i}"
                # )

                # if dict_src[i].get_attrs() != dict_dst[i].get_attrs():
                #     attrs = dict_src[i].get_attrs()
                #     for k, v in attrs.items():
                #         diff.add_item(k, v, getattr(dict_dst[i], k))

                # logger.debug(
                #     f"{dict_src[i].get_type()} {dict_dst[i]} | following the path for {dict_src[i].childs}"
                # )

                for child_type, child_attr in dict_src[key].__children__.items():

                    childs = self.diff_objects(
                        source=source_root.get_by_keys(
                            getattr(dict_src[key], child_attr), child_type
                        ),
                        dest=self.get_by_keys(
                            getattr(dict_dst[key], child_attr), child_type
                        ),
                        source_root=source_root,
                    )

                    for c in childs:
                        de.add_child(c)

                diffs.append(de)

        else:
            logger.warning(f"Type {type(source)} is not supported for now")

        return diffs

    def create_object(self, object_type, keys, params):
        self._crud_change(
            action="create", keys=keys, object_type=object_type, params=params
        )

    def update_object(self, object_type, keys, params):
        self._crud_change(
            action="update", object_type=object_type, keys=keys, params=params,
        )

    def delete_object(self, object_type, keys, params):
        self._crud_change(
            action="delete", object_type=object_type, keys=keys, params=params
        )

    def _crud_change(self, action, object_type, keys, params):

        if not hasattr(self, object_type):
            raise Exception("Unable to find this object type")

        # Check if a specific crud function is available
        #   update_interface or create_device etc ...
        # If not apply the default one
        if hasattr(self, f"{action}_{object_type}"):
            item = getattr(self, f"{action}_{object_type}")(keys=keys, params=params)
            logger.debug(f"{action}d {object_type} - {params}")
        else:
            item = getattr(self, f"default_{action}")(
                object_type=object_type, keys=keys, params=params
            )
            logger.debug(f"{action}d {object_type} = {keys} - {params} (default)")

        return item

    # ----------------------------------------------------------------------------
    def default_create(self, object_type, keys, params):
        """ """
        obj = getattr(self, object_type)
        item = obj(**keys, **params)
        self.add(item)
        return item

    def default_update(self, object_type, keys, params):
        raise NotImplementedError
        # obj = getattr(self, object_type)

        # item = session.query(obj).filter_by(**keys).first()
        # item.update(**params)
        # return item

    def default_delete(self, object_type, keys, params):
        obj = getattr(self, object_type)
        item = obj(**keys, **params)
        self.delete(item)
        return item

    # ------------------------------------------------------------------------------

    def get(self, obj, keys=[]):

        if isinstance(obj, str):
            modelname = obj
        else:
            modelname = obj.get_type()

        uid = "__".join(keys)

        if uid in self.__datas__[modelname]:
            return self.__datas__[modelname][uid]

        return None

    def get_all(self, obj):

        if isinstance(obj, str):
            modelname = obj
        else:
            modelname = obj.get_type()

        if not modelname in self.__datas__:
            return []

        return self.__datas__[modelname].values()

    def get_by_keys(self, keys, obj_type):

        return [value for uid, value in self.__datas__[obj_type].items() if uid in keys]

    def add(self, obj):

        modelname = obj.get_type()
        uid = obj.get_unique_id()

        if uid in self.__datas__[modelname]:
            raise Exception(f"Object {uid} already present")

        self.__datas__[modelname][uid] = obj

    def delete(self, obj):

        modelname = obj.get_type()
        uid = obj.get_unique_id()

        if uid not in self.__datas__[modelname]:
            raise Exception(f"Object {uid} not present")

        del self.__datas__[modelname][uid]