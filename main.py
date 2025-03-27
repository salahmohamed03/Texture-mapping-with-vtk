import os
import sys
import vtk
from vtk.util.numpy_support import numpy_to_vtk
import numpy as np
from PIL import Image
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QMainWindow, QApplication, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QFileDialog, QLabel
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from main import dicom_to_textured_ply

class PLYViewer(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(PLYViewer, self).__init__(parent)
        
        self.ply_file = None
        self.texture_file = None
        self.renderer = None
        self.render_window = None
        self.interactor = None
        self.actor = None
        self.texture_backup = None
        
        self._setup_ui()
        
    def _setup_ui(self):
        self.setWindowTitle("Medical Texture Mapping Viewer")
        self.resize(1000, 700)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        main_layout = QVBoxLayout()
        
        button_layout = QHBoxLayout()
        
        self.load_ply_btn = QPushButton("Load PLY")
        self.load_texture_btn = QPushButton("Load Texture")
        self.toggle_texture_btn = QPushButton("Toggle Texture")
        
        self.load_ply_btn.clicked.connect(self._on_load_ply)
        self.load_texture_btn.clicked.connect(self._on_load_texture)
        self.toggle_texture_btn.clicked.connect(self.toggle_texture)

        button_layout.addWidget(self.load_ply_btn)
        button_layout.addWidget(self.load_texture_btn)
        button_layout.addWidget(self.toggle_texture_btn)

        status_layout = QHBoxLayout()
        self.ply_label = QLabel("No PLY file loaded")
        self.texture_label = QLabel("No texture loaded")
        status_layout.addWidget(self.ply_label)
        status_layout.addWidget(self.texture_label)
        
        self.vtk_widget = QVTKRenderWindowInteractor(self.central_widget)
        
        main_layout.addLayout(button_layout)
        main_layout.addLayout(status_layout)
        main_layout.addWidget(self.vtk_widget)
        
        self.central_widget.setLayout(main_layout)
        
        self.render_window = self.vtk_widget.GetRenderWindow()
        
        self.renderer = vtk.vtkRenderer()
        self.render_window.AddRenderer(self.renderer)
        self.renderer.SetBackground(0.2, 0.3, 0.4) 
        
        self.interactor = self.vtk_widget
        
        style = vtk.vtkInteractorStyleTrackballCamera()
        self.interactor.SetInteractorStyle(style)
        
        self.interactor.Initialize()
        
        self._add_key_bindings()
        
    def _on_load_ply(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open PLY File", "", "PLY Files (*.ply);;All Files (*)"
        )
        
        if file_path:
            self.load_ply(file_path)
        
        self.toggle_texture()
        self.toggle_texture()
    
    def _on_load_texture(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Texture File", "", 
            "Image Files (*.png *.jpg *.jpeg);;All Files (*)"
        )
        
        if file_path:
            self.load_texture(file_path)
        
        self.toggle_texture() 
        self.toggle_texture()
    
    def generate_texture(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            dicom_to_textured_ply(folder_path)
            self.load_ply(folder_path + "/output.ply")
            self.load_texture(folder_path + "/output_texture.png")
            self.toggle_texture()
            self.toggle_texture()


    def load_ply(self, ply_file):
        if not os.path.exists(ply_file):
            self.ply_label.setText(f"Error: File not found: {ply_file}")
            return False
            
        self.ply_file = ply_file
        self.ply_label.setText(f"PLY: {os.path.basename(ply_file)}")
        
        self.renderer.RemoveAllViewProps()
        
        reader = vtk.vtkPLYReader()
        reader.SetFileName(self.ply_file)
        reader.Update()
        
        polydata = reader.GetOutput()
        print(f"PLY file loaded: {polydata.GetNumberOfPoints()} points, {polydata.GetNumberOfPolys()} polygons")
        
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(polydata)
        
        self.actor = vtk.vtkActor()
        self.actor.SetMapper(mapper)
        self.actor.GetProperty().SetColor(0.7, 0.7, 0.7) 
        
        self.actor.GetProperty().SetAmbient(0.2)
        self.actor.GetProperty().SetDiffuse(0.8)
        self.actor.GetProperty().SetSpecular(0.3)
        self.actor.GetProperty().SetSpecularPower(20)
        
        self.renderer.AddActor(self.actor)
        
        # Try to find and load texture with same name
        # try:
        #     base_path = os.path.splitext(ply_file)[0]
        #     for ext in ['_texture.png', '.png', '_texture.jpg', '.jpg']:
        #         texture_path = base_path + ext
        #         if os.path.exists(texture_path):
        #             self.load_texture(texture_path)
        #             break
        # except Exception as e:
        #     print(f"Auto texture loading error: {e}")
        
        self.renderer.ResetCamera()
        self.render_window.Render()
        self.toggle_texture()
        self.toggle_texture()
        
        return True
        
    def load_texture(self, texture_file):
        if not os.path.exists(texture_file):
            self.texture_label.setText(f"Error: Texture not found")
            return False
            
        self.texture_file = texture_file
        self.texture_label.setText(f"Texture: {os.path.basename(texture_file)}")
        
        if not self.actor:
            print("No model loaded. Please load a PLY file first.")
            return False
            
        try:
            texture = vtk.vtkTexture()
            
            _, ext = os.path.splitext(self.texture_file.lower())
            
            if ext in ['.jpg', '.jpeg']:
                reader = vtk.vtkJPEGReader()
                reader.SetFileName(self.texture_file)
                texture.SetInputConnection(reader.GetOutputPort())
            elif ext in ['.png']:
                reader = vtk.vtkPNGReader()
                reader.SetFileName(self.texture_file)
                texture.SetInputConnection(reader.GetOutputPort())
            else:
                img = Image.open(self.texture_file)
                if img.mode != "RGB":
                    img = img.convert("RGB")
                
                img_array = np.array(img)
                height, width, _ = img_array.shape
                
                img_data = img_array.reshape((-1, 3)).astype(np.uint8)
                vtk_data = numpy_to_vtk(img_data, deep=True)
                vtk_data.SetNumberOfComponents(3)
                
                image_data = vtk.vtkImageData()
                image_data.SetDimensions(width, height, 1)
                image_data.GetPointData().SetScalars(vtk_data)
                
                texture.SetInputData(image_data)
            
            texture.InterpolateOn()
            texture.MipmapOn()
            
            self.actor.SetTexture(texture)
            self.texture_backup = texture
            
            self.render_window.Render()
            
            print(f"Texture applied from: {self.texture_file}")
            return True
        except Exception as e:
            print(f"Error loading texture: {e}")
            self.texture_label.setText(f"Error loading texture")
            return False
    
    def _add_key_bindings(self):
        self.vtk_widget.AddObserver("KeyPressEvent", self._keypress_callback)
    
    def _keypress_callback(self, obj, event):
        key = obj.GetKeySym().lower()
        
        if key == 't':
            self.toggle_texture()
        elif key == 's':
            self.take_screenshot()
        elif key in ['x', 'y', 'z']:
            self._set_view_direction(key)
    
    def toggle_texture(self):
        if not self.actor:
            return
            
        if self.actor.GetTexture():
            self.texture_backup = self.actor.GetTexture()
            self.actor.SetTexture(None)
            self.actor.GetProperty().SetColor(0.7, 0.7, 0.7)
            print("Texture OFF")
            self.toggle_texture_btn.setText("Show Texture")
        else:
            if hasattr(self, 'texture_backup') and self.texture_backup:
                self.actor.SetTexture(self.texture_backup)
                self.actor.GetProperty().SetColor(1.0, 1.0, 1.0)
                print("Texture ON")
                self.toggle_texture_btn.setText("Hide Texture")
        self.render_window.Render()
    
    def take_screenshot(self):
        if not self.ply_file:
            print("No model loaded.")
            return
            
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save Screenshot", 
            os.path.splitext(self.ply_file)[0] + "_screenshot.png",
            "PNG Files (*.png)"
        )
        
        if not file_name:
            return
            
        w2if = vtk.vtkWindowToImageFilter()
        w2if.SetInput(self.render_window)
        w2if.Update()
        
        writer = vtk.vtkPNGWriter()
        writer.SetFileName(file_name)
        writer.SetInputConnection(w2if.GetOutputPort())
        writer.Write()
        
        print(f"Screenshot saved to: {file_name}")
    
    def _reset_camera(self):
        if not self.renderer:
            return
            
        self.renderer.ResetCamera()
        self.render_window.Render()
        print("Camera reset")
    
    def _set_view_direction(self, direction):
        if not self.renderer or not self.actor:
            return
            
        camera = self.renderer.GetActiveCamera()
        focal_point = camera.GetFocalPoint()
        position = camera.GetPosition()
        distance = np.sqrt(sum([(p - f) ** 2 for p, f in zip(position, focal_point)]))
        
        if direction == 'x':
            camera.SetPosition(focal_point[0] + distance, focal_point[1], focal_point[2])
            camera.SetViewUp(0, 0, 1)
            print("View along X axis")
        elif direction == 'y':
            camera.SetPosition(focal_point[0], focal_point[1] + distance, focal_point[2])
            camera.SetViewUp(0, 0, 1)
            print("View along Y axis")
            camera.SetPosition(focal_point[0], focal_point[1], focal_point[2] + distance)
            camera.SetViewUp(0, 1, 0)
            print("View along Z axis")
            
        self.renderer.ResetCameraClippingRange()
        self.render_window.Render()


def main():
    app = QApplication(sys.argv)
    window = PLYViewer()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
