bl_info = {
    "name": "DMD Import/Export",
    "author": "DMD Converter",
    "version": (1, 2, 0),
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
    """Парсер DMD формата с исправлениями согласно оригинальному движку"""
    
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
        """Парсит содержимое DMD файла с исправлениями"""
        mesh = DMDMesh()
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        current_section = ''
        i = 0
        
        print(f"Начинаем парсинг DMD файла, всего строк: {len(lines)}")
        
        while i < len(lines):
            line = lines[i]
            
            # Определяем объект
            if line.startswith('New object'):
                i += 1
                if i < len(lines):
                    mesh.object_name = lines[i].replace('()', '').strip()
                    print(f"Найден объект: {mesh.object_name}")
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
                print(f"Начинаем секцию: {current_section}")
                i += 1
                continue
            
            # Завершение секций
            if any(keyword in line.lower() for keyword in ['end', 'new']):
                if current_section:
                    if current_section == 'vertices':
                        print(f"Завершена секция vertices: {len(mesh.vertices)} вершин")
                    elif current_section == 'faces':
                        print(f"Завершена секция faces: {len(mesh.faces)} граней")
                    elif current_section == 'texture_vertices':
                        print(f"Завершена секция texture_vertices: {len(mesh.texture_vertices)} UV вершин")
                    elif current_section == 'texture_faces':
                        print(f"Завершена секция texture_faces: {len(mesh.texture_faces)} UV граней")
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
                    face_indices = [int(indices[0]) - 1, int(indices[1]) - 1, int(indices[2]) - 1]
                    if all(idx >= 0 for idx in face_indices):
                        mesh.faces.append(tuple(face_indices))
                    else:
                        print(f"Предупреждение: Невалидные индексы граней в строке: {line}")
            
            elif current_section == 'texture_vertices':
                coords = cls.NUMBER_REGEX.findall(line)
                # DMD формат хранит UV как 3 координаты (x, y, z), но используются только x и y
                if len(coords) >= 2:
                    mesh.texture_vertices.append((
                        float(coords[0]),
                        float(coords[1])
                    ))
            
            elif current_section == 'texture_faces':
                indices = cls.INTEGER_REGEX.findall(line)
                if len(indices) >= 3:
                    uv_indices = [int(indices[0]) - 1, int(indices[1]) - 1, int(indices[2]) - 1]
                    if all(idx >= 0 for idx in uv_indices):
                        mesh.texture_faces.append(tuple(uv_indices))
                    else:
                        print(f"Предупреждение: Невалидные UV индексы в строке: {line}")
            
            i += 1
        
        print(f"Парсинг завершен:")
        print(f"  Вершины: {len(mesh.vertices)}")
        print(f"  Грани: {len(mesh.faces)}")  
        print(f"  UV вершины: {len(mesh.texture_vertices)}")
        print(f"  UV грани: {len(mesh.texture_faces)}")
        
        return mesh

    @classmethod
    def write_file(cls, mesh: DMDMesh, filepath: str) -> None:
        """Записывает DMD меш в файл с правильным форматом согласно движку"""
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
            
            # Текстурные координаты с обязательной Z координатой = 0.0
            if mesh.texture_vertices:
                f.write("New Texture:\n")
                f.write("numtverts numtvfaces\n")
                f.write(f"   {len(mesh.texture_vertices):8}   {len(mesh.texture_faces):8}\n")
                
                f.write("Texture vertices:\n")
                for tvert in mesh.texture_vertices:
                    # В DMD формате UV всегда имеют 3 координаты, z=0.0
                    f.write(f"\t{tvert[0]:.6f} {tvert[1]:.6f} 0.000000\n")
                f.write("end texture vertices\n")
                
                f.write("Texture faces:\n")
                for tface in mesh.texture_faces:
                    f.write(f"\t{tface[0] + 1:6} {tface[1] + 1:6} {tface[2] + 1:6}\n")
                f.write("end texture faces\n")
                f.write("end of texture\n")
            
            f.write("end of file\n")


class ImportDMD(bpy.types.Operator, ImportHelper):
    """Импорт DMD файлов с исправлениями совместимости"""
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
    
    target_engine: bpy.props.EnumProperty(
        name="Target Engine",
        description="Target engine for UV compatibility",
        items=[
            ('BLENDER', "Blender Viewport", "Optimize UV for Blender display"),
            ('DMD_ENGINE', "DMD Engine", "Optimize UV for original DMD engine"),
            ('CUSTOM', "Custom", "Use manual UV inversion setting")
        ],
        default='BLENDER'
    )
    
    invert_v_custom: BoolProperty(
        name="Invert V (Custom)",
        description="Manually invert V coordinate (only used with Custom target)",
        default=True,
    )
    
    def execute(self, context):
        try:
            # Определяем настройки инверсии V в зависимости от целевого движка
            if self.target_engine == 'BLENDER':
                invert_v = True  # Для правильного отображения в Blender
            elif self.target_engine == 'DMD_ENGINE':
                invert_v = False  # DMD движок сам делает инверсию
            else:  # CUSTOM
                invert_v = self.invert_v_custom
            
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
            
            # ОБРАБОТКА UV КООРДИНАТ с учетом совместимости
            if dmd_mesh.texture_vertices and dmd_mesh.texture_faces:
                print(f"Обрабатываем UV: {len(dmd_mesh.texture_vertices)} UV вершин, {len(dmd_mesh.texture_faces)} UV граней")
                print(f"Инверсия V: {invert_v} (цель: {self.target_engine})")
                
                # Создаем UV слой
                mesh.uv_layers.new(name="UVMap")
                uv_layer = mesh.uv_layers.active.data
                
                # Убеждаемся что меш имеет индексы петель
                mesh.calc_loop_triangles()
                
                # UV грани соответствуют mesh граням 1:1
                if len(dmd_mesh.texture_faces) == len(dmd_mesh.faces):
                    print("UV грани соответствуют mesh граням 1:1")
                    
                    for poly_idx, poly in enumerate(mesh.polygons):
                        if poly_idx < len(dmd_mesh.texture_faces):
                            tex_face = dmd_mesh.texture_faces[poly_idx]
                            
                            for i, loop_idx in enumerate(poly.loop_indices):
                                if i < len(tex_face):
                                    # Определяем правильный индекс для UV
                                    if self.flip_faces and len(poly.loop_indices) == 3:
                                        tex_idx = 2 - i  # Обращаем порядок для треугольников
                                    else:
                                        tex_idx = i
                                    
                                    uv_idx = tex_face[tex_idx]
                                    
                                    # Проверяем границы и применяем UV
                                    if 0 <= uv_idx < len(dmd_mesh.texture_vertices):
                                        uv = dmd_mesh.texture_vertices[uv_idx]
                                        # Применяем инверсию V в зависимости от целевого движка
                                        if invert_v:
                                            uv_layer[loop_idx].uv = (uv[0], 1.0 - uv[1])
                                        else:
                                            uv_layer[loop_idx].uv = (uv[0], uv[1])
                                    else:
                                        print(f"Предупреждение: UV индекс {uv_idx} вне диапазона")
                                        uv_layer[loop_idx].uv = (0.0, 0.0)
                else:
                    print(f"Несоответствие UV данных: {len(dmd_mesh.texture_faces)} UV граней vs {len(dmd_mesh.faces)} mesh граней")
                    self.report({'WARNING'}, "Несоответствие UV данных в файле")
                
                # Принудительное обновление UV
                mesh.update()
            
            # Создаем объект
            obj = bpy.data.objects.new(dmd_mesh.object_name, mesh)
            context.collection.objects.link(obj)
            
            # Выделяем созданный объект
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            
            info_msg = f"Импортирован DMD: {len(vertices)} вершин, {len(faces)} граней"
            if dmd_mesh.texture_vertices:
                info_msg += f", UV: {self.target_engine} режим"
            self.report({'INFO'}, info_msg)
            return {'FINISHED'}
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Ошибка импорта DMD: {str(e)}")
            return {'CANCELLED'}


class ExportDMD(bpy.types.Operator, ExportHelper):
    """Экспорт DMD файлов с исправлениями совместимости"""
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
    
    target_engine: bpy.props.EnumProperty(
        name="Target Engine",
        description="Target engine for UV compatibility",
        items=[
            ('BLENDER', "Blender Viewport", "UV for Blender import (with pre-inversion)"),
            ('DMD_ENGINE', "DMD Engine", "UV for original DMD engine (no pre-inversion)"),
            ('CUSTOM', "Custom", "Use manual UV inversion setting")
        ],
        default='DMD_ENGINE'
    )
    
    invert_v_custom: BoolProperty(
        name="Invert V (Custom)",
        description="Manually invert V coordinate (only used with Custom target)",
        default=False,
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
        
        info_msg = f"Экспортирован DMD: {len(dmd_mesh.vertices)} вершин, {len(dmd_mesh.faces)} граней"
        if dmd_mesh.texture_vertices:
            info_msg += f", UV: {self.target_engine} режим"
        self.report({'INFO'}, info_msg)
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
        
        info_msg = f"Экспортировано {exported_count} объектов в отдельные DMD файлы"
        if exported_count > 0:
            info_msg += f", UV: {self.target_engine} режим"
        self.report({'INFO'}, info_msg)
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
        
        info_msg = f"Экспортировано {len(mesh_objects)} объектов в единый DMD файл: {len(combined_mesh.vertices)} вершин, {len(combined_mesh.faces)} граней"
        if combined_mesh.texture_vertices:
            info_msg += f", UV: {self.target_engine} режим"
        self.report({'INFO'}, info_msg)
        return {'FINISHED'}
    
    def object_to_dmd_mesh(self, context, obj):
        """Конвертирует Blender объект в DMD меш с правильной обработкой UV для разных движков"""
        # Определяем настройки инверсии V в зависимости от целевого движка
        if self.target_engine == 'BLENDER':
            invert_v = True  # Для последующего импорта в Blender
        elif self.target_engine == 'DMD_ENGINE':
            invert_v = False  # DMD движок сам делает инверсию "1-v"
        else:  # CUSTOM
            invert_v = self.invert_v_custom
        
        print(f"Экспорт UV: инверсия V = {invert_v} (цель: {self.target_engine})")
        
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
        
        # ИСПРАВЛЕННЫЙ ЭКСПОРТ UV КООРДИНАТ с учетом целевого движка
        if self.export_uv and mesh.uv_layers:
            uv_layer = mesh.uv_layers.active.data
            
            print(f"Экспорт UV для объекта {obj.name}")
            print(f"Полигонов: {len(mesh.polygons)}")
            
            # Создаем UV данные per-face, как требует DMD формат
            face_uv_vertices = []
            face_uv_indices = []
            
            for poly_idx, poly in enumerate(mesh.polygons):
                if len(poly.vertices) == 3:  # Только треугольники
                    face_uvs = []
                    
                    for i, loop_idx in enumerate(poly.loop_indices):
                        uv = uv_layer[loop_idx].uv
                        
                        # КРИТИЧНО: Применяем инверсию V в зависимости от целевого движка
                        if invert_v:
                            # Для Blender - инвертируем заранее, чтобы при импорте с "1-v" получить правильное
                            uv_coord = (uv[0], 1.0 - uv[1])
                        else:
                            # Для DMD движка - не инвертируем, движок сам применит "1-v"
                            uv_coord = (uv[0], uv[1])
                        
                        face_uv_vertices.append(uv_coord)
                        face_uvs.append(len(face_uv_vertices) - 1)
                    
                    # Применяем flip_faces к UV тоже
                    if self.flip_faces:
                        face_uvs = [face_uvs[2], face_uvs[1], face_uvs[0]]
                    
                    face_uv_indices.append(tuple(face_uvs))
            
            dmd_mesh.texture_vertices = face_uv_vertices
            dmd_mesh.texture_faces = face_uv_indices
            
            print(f"Создано UV вершин: {len(dmd_mesh.texture_vertices)}")
            print(f"Создано UV граней: {len(dmd_mesh.texture_faces)}")
        
        # Освобождаем меш
        obj_eval.to_mesh_clear()
        
        return dmd_mesh


def menu_func_import(self, context):
    self.layout.operator(ImportDMD.bl_idname, text="DMD (.dmd)")


def menu_func_export(self, context):
    self.layout.operator(ExportDMD.bl_idname, text="DMD (.dmd)")


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
    DMD_FH_import,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    
    print("DMD Import/Export аддон зарегистрирован (финальная версия с совместимостью)")


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()