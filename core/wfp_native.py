"""Native WFP ABI declarations. No API is called at import time.

GUIDs: microsoft/win32metadata fwpmu.h. Structures: Windows SDK fwptypes.h,
fwpmtypes.h. Only fixed-width Windows types are used (including on test hosts).
"""
import ctypes as C
import uuid
U8,U16,U32,U64=C.c_uint8,C.c_uint16,C.c_uint32,C.c_uint64
P=C.c_void_p
class GUID(C.Structure):
    _fields_=[('a',U32),('b',U16),('c',U16),('d',U8*8)]
    @classmethod
    def of(cls,value): return cls.from_buffer_copy(uuid.UUID(str(value)).bytes_le)
class Blob(C.Structure): _fields_=[('size',U32),('data',P)]
class Display(C.Structure): _fields_=[('name',C.c_wchar_p),('description',C.c_wchar_p)]
class ValueUnion(C.Union):
    _fields_=[('u8',U8),('u16',U16),('u32',U32),('pointer',P),('double',C.c_double)]
class Value(C.Structure): _fields_=[('type',U32),('value',ValueUnion)]
class Condition(C.Structure): _fields_=[('key',GUID),('match',U32),('value',Value)]
class Action(C.Structure): _fields_=[('type',U32),('key',GUID)]
class Context(C.Union): _fields_=[('raw',U64),('key',GUID)]
class Filter(C.Structure):
    _fields_=[('key',GUID),('display',Display),('flags',U32),('provider',P),
              ('data',Blob),('layer',GUID),('sublayer',GUID),('weight',Value),
              ('count',U32),('conditions',C.POINTER(Condition)),('action',Action),
              ('context',Context),('reserved',P),('id',U64),('effective_weight',Value)]
class Sublayer(C.Structure):
    _fields_=[('key',GUID),('display',Display),('flags',U32),('provider',P),('data',Blob),('weight',U16)]
KEYS={
'packet4':'1e5c9fae-8a84-4135-a331-950b54229ecd','packet6':'a3b3ab6b-3564-488c-9117-f34e82142763',
'connect4':'c38d57d1-05a7-4c33-904f-7fbceee60e82','connect6':'4a72393b-319f-44bc-84c3-ba54dcb3b6b4',
'accept4':'e1cd9fe7-f4b5-4273-96c0-592e487b8650','accept6':'a3b42c97-9f04-4672-b87e-cee9c483257f',
'app':'d78e1e87-8644-4ea5-9437-d809ecefc971','remote':'b235ae9a-1d64-49b8-a44c-5ff3d9095045',
'port':'c35a604d-d22b-4e1a-91b4-68f674ee674b','protocol':'3971ef2b-623e-4f9a-8cb1-6e79b806b9a7',
'interface':'4cd62a49-59c3-4969-b7f3-bda5d32890a4','flags':'632ce23b-5167-435c-86d7-e903684aa80c'}

class EnumTemplate(C.Structure):
    _fields_=[('provider',P),('layer',GUID),('enum_type',U32),('flags',U32),
              ('context',P),('count',U32),('conditions',P),('action_mask',U32),('callout',P)]
