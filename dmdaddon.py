bl_info = {
    "name": "DMD Import/Export",
    "author": "DMD Converter",
    "version": (1, 0, 0),
    "blender": (4, 5, 0),
    "location": "File > Import/Export",
    "description": "Import and Export DMD (3D Model Data) files",
    "warning": "",
    "wiki_url": "",
    "category": "Import-Export",
}

import bpy
import bmesh
import re
from bpy.props import StringProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper
from mathutils import Vector
import os
from pathlib import Path
from typing import List, Tuple, Optional


class DMDMesh:
    """Класс для представления DMD меша"""
    def __init__(self):
        self.vertices = []
        self.faces = []
        self.texture_vertices = []
        self.texture_faces = []
        self.object_name = "TriMesh"


class DMDParser:
    """Парсер DMD формата"""
    
    NUMBER_REGEX = re.compile(r'-?\d+\.?\d*(?:[eE][+-]?\d+)?')
    INTEGER_REGEX = re.compile(r'\d+')
    
    @classmethod
    def parse_file(cls, filepath: str) -> DMDMesh:
        """Парсит DMD файл"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Пробуем другие кодировки
            for encoding in ['cp1251', 'latin-1']:
                try:
                    with open(filepath, 'r', encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError(f"Не удалось прочитать файл {filepath}")
        
        return cls._parse_content(content)
    
    @classmethod
    def _parse_content(cls, content: str) -> DMDMesh:
        """Парсит содержимое DMD файла"""
        mesh = DMDMesh()
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        current_section = ''
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Определяем объект
            if line.startswith('New object'):
                i += 1
                if i < len(lines):
                    mesh.object_name = lines[i].replace('()', '').strip()
                i += 1
                continue
            
            # Определяем секции
            section_map = {
                'Mesh vertices:': 'vertices',
                'Mesh faces:': 'faces', 
                'Texture vertices:': 'texture_vertices',
                'Texture faces:': 'texture_faces'
            }
            
            if line in section_map:
                current_section = section_map[line]
                i += 1
                continue
            
            # Завершение секций
            if any(keyword in line.lower() for keyword in ['end', 'new']):
                current_section = ''
                i += 1
                continue
            
            # Парсим данные
            if current_section == 'vertices':
                coords = cls.NUMBER_REGEX.findall(line)
                if len(coords) >= 3:
                    mesh.vertices.append((
                        float(coords[0]),
                        float(coords[1]),
                        float(coords[2])
                    ))
            
            elif current_section == 'faces':
                indices = cls.INTEGER_REGEX.findall(line)
                if len(indices) >= 3:
                    mesh.faces.append((
                        int(indices[0]) - 1,  # Конвертируем из 1-based в 0-based
                        int(indices[1]) - 1,
                        int(indices[2]) - 1
                    ))
            
            elif current_section == 'texture_vertices':
                coords = cls.NUMBER_REGEX.findall(line)
                if len(coords) >= 2:
                    mesh.texture_vertices.append((
                        float(coords[0]),
                        float(coords[1])
                    ))
            
            elif current_section == 'texture_faces':
                indices = cls.INTEGER_REGEX.findall(line)
                if len(indices) >= 3:
                    mesh.texture_faces.append((
                        int(indices[0]) - 1,
                        int(indices[1]) - 1,
                        int(indices[2]) - 1
                    ))
            
            i += 1
        
        return mesh

    @classmethod
    def write_file(cls, mesh: DMDMesh, filepath: str) -> None:
        """Записывает DMD меш в файл"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("New object\n")
            f.write(f"{mesh.object_name}()\n")
            f.write("numverts numfaces\n")
            f.write(f"   {len(mesh.vertices):8}   {len(mesh.faces):8}\n")
            
            f.write("Mesh vertices:\n")
            for vertex in mesh.vertices:
                f.write(f"\t{vertex[0]:.6f} {vertex[1]:.6f} {vertex[2]:.6f}\n")
            f.write("end vertices\n")
            
            f.write("Mesh faces:\n")
            for face in mesh.faces:
                # Конвертируем обратно в 1-based индексы
                f.write(f"\t{face[0] + 1:6} {face[1] + 1:6} {face[2] + 1:6}\n")
            f.write("end faces\n")
            f.write("end mesh\n")
            
            # Текстурные координаты
            if mesh.texture_vertices:
                f.write("New Texture:\n")
                f.write("numtverts numtvfaces\n")
                f.write(f"   {len(mesh.texture_vertices):8}   {len(mesh.texture_faces):8}\n")
                
                f.write("Texture vertices:\n")
                for tvert in mesh.texture_vertices:
                    f.write(f"\t{tvert[0]:.6f} {tvert[1]:.6f} 0.000000\n")
                f.write("end texture vertices\n")
                
                f.write("Texture faces:\n")
                for tface in mesh.texture_faces:
                    f.write(f"\t{tface[0] + 1:6} {tface[1] + 1:6} {tface[2] + 1:6}\n")
                f.write("end texture faces\n")
                f.write("end of texture\n")
            
            f.write("end of file\n")


class ImportDMD(bpy.types.Operator, ImportHelper):
    """Импорт DMD файлов"""
    bl_idname = "import_mesh.dmd"
    bl_label = "Import DMD"
    bl_description = "Import DMD mesh files"
    
    filename_ext = ".dmd"
    filter_glob: StringProperty(
        default="*.dmd",
        options={'HIDDEN'},
        maxlen=255,
    )
    
    flip_y: BoolProperty(
        name="Flip Y",
        description="Flip Y coordinate",
        default=False,
    )
    
    flip_z: BoolProperty(
        name="Flip Z", 
        description="Flip Z coordinate",
        default=False,
    )
    
    flip_faces: BoolProperty(
        name="Flip Faces",
        description="Reverse face normals",
        default=False,
    )
    
    def execute(self, context):
        try:
            # Парсим DMD файл
            dmd_mesh = DMDParser.parse_file(self.filepath)
            
            # Создаем меш в Blender
            mesh = bpy.data.meshes.new(dmd_mesh.object_name)
            
            # Трансформируем вершины если нужно
            vertices = []
            for vertex in dmd_mesh.vertices:
                x, y, z = vertex
                if self.flip_y:
                    y = -y
                if self.flip_z:
                    z = -z
                vertices.append((x, y, z))
            
            # Трансформируем грани если нужно
            faces = []
            for face in dmd_mesh.faces:
                if self.flip_faces:
                    faces.append((face[2], face[1], face[0]))
                else:
                    faces.append(face)
            
            # Создаем меш
            mesh.from_pydata(vertices, [], faces)
            mesh.update()
            
            # Добавляем UV координаты если есть
            if dmd_mesh.texture_vertices and dmd_mesh.texture_faces:
                # Создаем UV слой
                mesh.uv_layers.new(name="UVMap")
                uv_layer = mesh.uv_layers.active.data
                
                # Проверяем соответствие граней
                if len(dmd_mesh.texture_faces) == len(dmd_mesh.faces):
                    # UV грани соответствуют обычным граням
                    for poly_idx, poly in enumerate(mesh.polygons):
                        tex_face = dmd_mesh.texture_faces[poly_idx]
                        
                        for i, loop_idx in enumerate(poly.loop_indices):
                            if self.flip_faces:
                                uv_idx = tex_face[2-i]  # Обращаем порядок для UV тоже
                            else:
                                uv_idx = tex_face[i]
                            
                            if uv_idx < len(dmd_mesh.texture_vertices):
                                uv = dmd_mesh.texture_vertices[uv_idx]
                                uv_layer[loop_idx].uv = (uv[0], 1.0 - uv[1])  # Инвертируем V
                
                elif len(dmd_mesh.texture_vertices) == len(dmd_mesh.vertices):
                    # UV вершины соответствуют обычным вершинам 1:1
                    for poly in mesh.polygons:
                        for i, loop_idx in enumerate(poly.loop_indices):
                            vert_idx = poly.vertices[i]
                            if vert_idx < len(dmd_mesh.texture_vertices):
                                uv = dmd_mesh.texture_vertices[vert_idx]
                                uv_layer[loop_idx].uv = (uv[0], 1.0 - uv[1])  # Инвертируем V
            
            # Создаем объект
            obj = bpy.data.objects.new(dmd_mesh.object_name, mesh)
            context.collection.objects.link(obj)
            
            # Выделяем созданный объект
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            
            self.report({'INFO'}, f"Импортирован DMD: {len(vertices)} вершин, {len(faces)} граней")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Ошибка импорта DMD: {str(e)}")
            return {'CANCELLED'}


class ExportDMD(bpy.types.Operator, ExportHelper):
    """Экспорт DMD файлов"""
    bl_idname = "export_mesh.dmd"
    bl_label = "Export DMD"
    bl_description = "Export selected mesh to DMD format"
    
    filename_ext = ".dmd"
    filter_glob: StringProperty(
        default="*.dmd",
        options={'HIDDEN'},
        maxlen=255,
    )
    
    export_mode: bpy.props.EnumProperty(
        name="Export Mode",
        description="Choose what to export",
        items=[
            ('ACTIVE', "Active Object", "Export only active object"),
            ('SELECTED', "Selected Objects", "Export all selected objects to separate files"),
            ('ALL_MESH', "All Mesh Objects", "Export all mesh objects in scene to separate files"),
            ('COMBINED', "Combine All", "Combine all mesh objects into one DMD file")
        ],
        default='ACTIVE'
    )
    
    flip_y: BoolProperty(
        name="Flip Y",
        description="Flip Y coordinate", 
        default=False,
    )
    
    flip_z: BoolProperty(
        name="Flip Z",
        description="Flip Z coordinate",
        default=False,
    )
    
    flip_faces: BoolProperty(
        name="Flip Faces", 
        description="Reverse face normals",
        default=False,
    )
    
    triangulate: BoolProperty(
        name="Triangulate",
        description="Triangulate mesh before export",
        default=True,
    )
    
    export_uv: BoolProperty(
        name="Export UV",
        description="Export UV coordinates",
        default=True,
    )
    
    def execute(self, context):
        try:
            if self.export_mode == 'ACTIVE':
                return self.export_single_object(context, context.active_object)
            
            elif self.export_mode == 'SELECTED':
                return self.export_multiple_objects(context, context.selected_objects)
            
            elif self.export_mode == 'ALL_MESH':
                mesh_objects = [obj for obj in context.scene.objects if obj.type == 'MESH']
                return self.export_multiple_objects(context, mesh_objects)
            
            elif self.export_mode == 'COMBINED':
                mesh_objects = [obj for obj in context.scene.objects if obj.type == 'MESH']
                return self.export_combined_objects(context, mesh_objects)
                
        except Exception as e:
            self.report({'ERROR'}, f"Ошибка экспорта DMD: {str(e)}")
            return {'CANCELLED'}
    
    def export_single_object(self, context, obj):
        """Экспорт одного объекта"""
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Выберите меш-объект для экспорта")
            return {'CANCELLED'}
        
        dmd_mesh = self.object_to_dmd_mesh(context, obj)
        DMDParser.write_file(dmd_mesh, self.filepath)
        
        self.report({'INFO'}, f"Экспортирован DMD: {len(dmd_mesh.vertices)} вершин, {len(dmd_mesh.faces)} граней")
        return {'FINISHED'}
    
    def export_multiple_objects(self, context, objects):
        """Экспорт нескольких объектов в отдельные файлы"""
        mesh_objects = [obj for obj in objects if obj.type == 'MESH']
        
        if not mesh_objects:
            self.report({'ERROR'}, "Нет меш-объектов для экспорта")
            return {'CANCELLED'}
        
        base_path = os.path.splitext(self.filepath)[0]
        exported_count = 0
        
        for obj in mesh_objects:
            try:
                # Создаем имя файла для каждого объекта
                obj_filepath = f"{base_path}_{obj.name}.dmd"
                
                dmd_mesh = self.object_to_dmd_mesh(context, obj)
                DMDParser.write_file(dmd_mesh, obj_filepath)
                exported_count += 1
                
            except Exception as e:
                self.report({'WARNING'}, f"Ошибка экспорта объекта {obj.name}: {str(e)}")
        
        self.report({'INFO'}, f"Экспортировано {exported_count} объектов в отдельные DMD файлы")
        return {'FINISHED'}
    
    def export_combined_objects(self, context, objects):
        """Экспорт всех объектов в один DMD файл"""
        mesh_objects = [obj for obj in objects if obj.type == 'MESH']
        
        if not mesh_objects:
            self.report({'ERROR'}, "Нет меш-объектов для экспорта")
            return {'CANCELLED'}
        
        # Создаем объединенный DMD меш
        combined_mesh = DMDMesh()
        combined_mesh.object_name = "Combined_Scene"
        
        vertex_offset = 0
        uv_offset = 0
        
        for obj in mesh_objects:
            try:
                dmd_mesh = self.object_to_dmd_mesh(context, obj)
                
                # Добавляем вершины
                combined_mesh.vertices.extend(dmd_mesh.vertices)
                
                # Добавляем грани с учетом смещения вершин
                for face in dmd_mesh.faces:
                    new_face = (
                        face[0] + vertex_offset,
                        face[1] + vertex_offset,
                        face[2] + vertex_offset
                    )
                    combined_mesh.faces.append(new_face)
                
                # Добавляем UV координаты
                if dmd_mesh.texture_vertices:
                    combined_mesh.texture_vertices.extend(dmd_mesh.texture_vertices)
                    
                    for tex_face in dmd_mesh.texture_faces:
                        new_tex_face = (
                            tex_face[0] + uv_offset,
                            tex_face[1] + uv_offset,
                            tex_face[2] + uv_offset
                        )
                        combined_mesh.texture_faces.append(new_tex_face)
                    
                    uv_offset += len(dmd_mesh.texture_vertices)
                
                vertex_offset += len(dmd_mesh.vertices)
                
            except Exception as e:
                self.report({'WARNING'}, f"Ошибка обработки объекта {obj.name}: {str(e)}")
        
        DMDParser.write_file(combined_mesh, self.filepath)
        
        self.report({'INFO'}, f"Экспортировано {len(mesh_objects)} объектов в единый DMD файл: {len(combined_mesh.vertices)} вершин, {len(combined_mesh.faces)} граней")
        return {'FINISHED'}
    
    def object_to_dmd_mesh(self, context, obj):
        """Конвертирует Blender объект в DMD меш"""
        # Создаем копию меша для модификации
        depsgraph = context.evaluated_depsgraph_get()
        obj_eval = obj.evaluated_get(depsgraph)
        mesh = obj_eval.to_mesh()
        
        # Применяем трансформацию объекта к вершинам
        mesh.transform(obj.matrix_world)
        
        # Триангулируем если нужно
        if self.triangulate:
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bmesh.ops.triangulate(bm, faces=bm.faces[:])
            bm.to_mesh(mesh)
            bm.free()
        
        mesh.calc_loop_triangles()
        
        # Создаем DMD меш
        dmd_mesh = DMDMesh()
        dmd_mesh.object_name = obj.name
        
        # Экспортируем вершины
        for vertex in mesh.vertices:
            co = vertex.co
            x, y, z = co.x, co.y, co.z
            
            if self.flip_y:
                y = -y
            if self.flip_z:
                z = -z
                
            dmd_mesh.vertices.append((x, y, z))
        
        # Экспортируем грани
        for poly in mesh.polygons:
            if len(poly.vertices) == 3:  # Только треугольники
                face = list(poly.vertices)
                if self.flip_faces:
                    face = [face[2], face[1], face[0]]
                dmd_mesh.faces.append(tuple(face))
        
        # Экспортируем UV координаты
        if self.export_uv and mesh.uv_layers:
            uv_layer = mesh.uv_layers.active.data
            
            # Собираем уникальные UV координаты
            uv_dict = {}
            uv_list = []
            
            for poly in mesh.polygons:
                if len(poly.vertices) == 3:
                    face_uvs = []
                    for loop_idx in poly.loop_indices:
                        uv = uv_layer[loop_idx].uv
                        # Инвертируем V обратно для DMD формата
                        uv_coord = (uv[0], 1.0 - uv[1])
                        
                        # Ищем или создаем индекс для этой UV координаты
                        uv_key = (round(uv_coord[0], 6), round(uv_coord[1], 6))
                        if uv_key not in uv_dict:
                            uv_dict[uv_key] = len(uv_list)
                            uv_list.append(uv_coord)
                        
                        face_uvs.append(uv_dict[uv_key])
                    
                    if self.flip_faces:
                        face_uvs = [face_uvs[2], face_uvs[1], face_uvs[0]]
                    
                    dmd_mesh.texture_faces.append(tuple(face_uvs))
            
            dmd_mesh.texture_vertices = uv_list
        
        # Освобождаем меш
        obj_eval.to_mesh_clear()
        
        return dmd_mesh


def menu_func_import(self, context):
    self.layout.operator(ImportDMD.bl_idname, text="DMD (.dmd)")


def menu_func_export(self, context):
    self.layout.operator(ExportDMD.bl_idname, text="DMD (.dmd)")


def dmd_drop_handler(context, event):
    """Обработчик drag & drop для DMD файлов"""
    if not hasattr(event, 'location') or not hasattr(event, 'type'):
        return False
    
    # Проверяем, является ли это событием перетаскивания файла
    if event.type == 'EVT_DROP':
        if hasattr(context, 'window_manager') and hasattr(context.window_manager, 'clipboard'):
            try:
                # Получаем путь к файлу из clipboard (если он там есть)
                filepath = context.window_manager.clipboard
                if filepath and filepath.lower().endswith('.dmd'):
                    # Вызываем импорт DMD
                    bpy.ops.import_mesh.dmd('EXEC_DEFAULT', filepath=filepath)
                    return True
            except:
                pass
    
    return False


class DMD_OT_drop_handler(bpy.types.Operator):
    """Обработчик для drag & drop DMD файлов"""
    bl_idname = "wm.dmd_drop_handler"
    bl_label = "DMD Drop Handler"
    bl_options = {'REGISTER', 'INTERNAL'}
    
    filepath: StringProperty()
    
    def execute(self, context):
        if self.filepath.lower().endswith('.dmd'):
            try:
                # Импортируем DMD файл
                bpy.ops.import_mesh.dmd('EXEC_DEFAULT', filepath=self.filepath)
                self.report({'INFO'}, f"Импортирован DMD файл: {os.path.basename(self.filepath)}")
            except Exception as e:
                self.report({'ERROR'}, f"Ошибка импорта DMD: {str(e)}")
        return {'FINISHED'}


def register_drag_drop():
    """Регистрация drag & drop обработчика"""
    try:
        # Регистрируем обработчик для файлов .dmd
        def drop_handler_func(context):
            # Получаем все файлы из drag & drop события
            dropped_files = getattr(context.window_manager, 'clipboard', '')
            if dropped_files:
                files = dropped_files.split('\n')
                for filepath in files:
                    filepath = filepath.strip()
                    if filepath.lower().endswith('.dmd') and os.path.exists(filepath):
                        bpy.ops.wm.dmd_drop_handler('EXEC_DEFAULT', filepath=filepath)
                        return True
            return False
        
        # Добавляем в глобальные обработчики
        if not hasattr(bpy.app.handlers, 'dmd_drop_handlers'):
            bpy.app.handlers.dmd_drop_handlers = []
        
        bpy.app.handlers.dmd_drop_handlers.append(drop_handler_func)
        
    except Exception as e:
        print(f"Не удалось зарегистрировать drag & drop обработчик: {e}")


def unregister_drag_drop():
    """Удаление drag & drop обработчика"""
    try:
        if hasattr(bpy.app.handlers, 'dmd_drop_handlers'):
            bpy.app.handlers.dmd_drop_handlers.clear()
    except:
        pass


# Альтернативный метод через Space Handler
class DMD_OT_space_drop(bpy.types.SpaceView3D):
    """Обработчик перетаскивания в 3D окне"""
    
    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D'
    
    def invoke(self, context, event):
        # Проверяем drag & drop события
        if event.type == 'EVT_DROP' and hasattr(context, 'active_operator'):
            try:
                # Попытка получить информацию о перетаскиваемом файле
                if hasattr(event, 'ascii') and event.ascii:
                    filepath = str(event.ascii)
                    if filepath.lower().endswith('.dmd'):
                        bpy.ops.import_mesh.dmd('INVOKE_DEFAULT', filepath=filepath)
                        return {'FINISHED'}
            except:
                pass
        
        return {'PASS_THROUGH'}


# Простой обработчик через файловый браузер
class DMD_FH_import(bpy.types.FileHandler):
    """File handler для DMD файлов"""
    bl_idname = "DMD_FH_import"
    bl_label = "Import DMD"
    bl_import_operator = "import_mesh.dmd"
    bl_file_extensions = ".dmd"
    
    @classmethod
    def poll_drop(cls, context):
        return (context.area and context.area.type == 'VIEW_3D')


classes = (
    ImportDMD,
    ExportDMD,
    DMD_OT_drop_handler,
    DMD_FH_import,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    
    # Регистрируем drag & drop
    register_drag_drop()
    
    print("DMD Import/Export аддон зарегистрирован с поддержкой drag & drop")


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    
    # Удаляем drag & drop обработчики
    unregister_drag_drop()
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()