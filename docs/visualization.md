# Visualization

Code: `src/voxeltrace/visualization/` (renderer version `vt-render-1`).

The renderer is deterministic and display-only. It produces PNGs for human review and as
multimodal model input.

## Guarantees

- **Quantitative arrays are never modified.** Windowing and colour maps act on a copy.
  `RenderParams` records them: SUV window, colour map, CT centre/width, PET alpha, scale and
  crop.
- **Display normalisation and quantitative values are kept separate.** Pixel colours are
  display indices `floor(clip((v − lo)/(hi − lo)) · 255 + 0.5)`, not SUV values. Any number
  drawn on an image is taken verbatim from the evidence JSON and listed in `displayed_values`
  with its JSON path.
- **No interpolation of PET.** Each voxel becomes an exact `scale_x × scale_y` pixel block
  (nearest neighbour). CT is linearly resampled onto the PET grid **for display only**, via
  SimpleITK in physical (LPS) space, and only if both series share the FrameOfReferenceUID.
- **Outlines come only from supplied segmentations**: the 4-neighbour inner boundary of the
  block-expanded reference mask. VoxelTrace never infers a lesion outline.
- **Deterministic:** the same arrays and parameters give byte-identical PNGs (tested).
- **No patient identifiers.** Footers show the view, window, convention, scale bar and evidence
  values only.

## Orientation

- Only the standard axial orientation (ImageOrientationPatient = 1,0,0,0,1,0) is rendered.
  Anything else raises `RenderError`; images are not silently reoriented.
- **Radiological** (default): image left = patient **right**, top = **anterior**. For the
  standard orientation this is the natural array layout (column i → image x, row j → image y).
- **Neurological**: mirrored x (image left = patient left). It is recorded in `convention`.
- **Coronal MIP**:
  - Maximum over the anterior–posterior axis (j), seen from the front, with superior at the
    top. Rows are flipped because k increases from inferior to superior.
  - The pixel aspect may be anisotropic. `mm_per_px_x` and `mm_per_px_y` are recorded, and the
    vertical scale factor is `round(scale · Δz/Δx)`.

## Coordinates (exact)

- **Voxel ↔ patient:** `voxel_to_patient(geometry, (k, j, i))` uses the DICOM affine (LPS mm).
  `patient_to_voxel` is its inverse.
- **Voxel ↔ rendered pixel:** `PlaneMapping` (crop origin, crop size, scale, flips).
  - `voxel_block(a, b)` gives the inclusive pixel block of a voxel.
  - `voxel_to_px` gives the integer pixel at the block centre.
  - `px_to_voxel` is the exact inverse for every pixel.
  - Blocks tile the image exactly (tested for every voxel, with flips and crops).
- **Labels** go in a footer strip appended **below** the image, so pixel coordinates inside the
  image region are unchanged.

## Views

| View | Function | Default |
|---|---|---|
| PET axial | `pet_axial` | SUV window 0–8 g/mL, inverted greyscale |
| CT axial | `ct_axial` (on the PET grid) | soft tissue C40/W400 HU |
| PET/CT fused | `fused_axial` | CT grey + "hot" PET, weight = normalised SUV × 0.7 |
| Segmentation overlay | `annotations.draw` | cyan outline (drawn last, so it is exact) |
| SUVmax marker | crosshair (green) with a gap, so the voxel stays visible | |
| SUVpeak marker | circle (magenta): the 1 cm³ sphere ∩ slice, r = √(6.2035² − dz²) mm | |
| Bounding box | yellow rectangle drawn just outside the inclusive box | |
| PET MIP | `pet_coronal_mip` | coronal, superior at top |
| Lesion crop | `crop_box` | 80 mm window, shifted inside the image (no padding) |
| Scale bar | `add_footer(scale_bar_mm=…)` | |

## Consistency checks (`verify_axial_render`)

Generation **fails** if any of these does not hold:
- the rendered mask pixel count equals the slice voxel count × block size;
- the bbox annotation equals the rendered mask extent;
- every outline pixel has exactly the outline colour;
- the SUVmax marker maps back to the SUVmax voxel, and the SUV there equals SUVmax;
- the displayed lesion id equals the rendered segment;
- every displayed number equals the value at its evidence-JSON path.
