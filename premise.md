# Study Premise: 3 mm vs 8 mm Robotic Tools for TORS Cleft Palate Repair

## Goal

Show that our lab's 3 mm robotic tools can do cleft palate repair in a pig model.
Compare them with the standard 8 mm da Vinci tools.

## What we want to show

1. **Feasibility:** the 3 mm tools can do the full repair.
2. **Efficacy:** the 3 mm repair is as good as the 8 mm repair.
3. **Advantages:** the 3 mm tools are better on some measures.

## 1. Feasibility

- Every step of the repair was completed.
- No switch to the 8 mm tools or to manual surgery.
- Count of tool failures and dropped needles.
- Setup time for each system.

## 2. Efficacy

- How well the closure holds: gaps, suture spacing, bite depth.
- Set the "close enough" margin before looking at the data.

## 3. Advantages

Main measures:

- **Visual field:** the instruments cover less of the camera image.
- **Peak force on tissue:** lower force, so less damage to tissue.
- **Time per suture:** faster suturing.

Supporting measures:

- Fewer collisions between tools, or with teeth and retractor.
- Fewer clutch and reposition events.
- Reach further back in the palate.

Notes:

- Report every measure we compute, even where the 8 mm tools win.
- Lower force must be shown with the feasibility results.
  Otherwise readers may think the 3 mm tools are too weak.

## Data

- **Stereo endoscope video:** surgical steps, visual field, collisions, suture timing.
- **Rosbags:** tool motion, grip, timing, and possibly joint effort for force.

## How to measure peak force

Use the best option the data allows:

2. Estimate from joint effort or motor current in the rosbags.
3. Jaw grip effort, for squeezing force.
4. Tissue deformation in the stereo video (weakest).

## How to measure time per suture

- Start: needle first touches tissue.
- End: knot is tightened or suture is cut.
- Report each suture layer (nasal, muscle, oral) separately.

## Other measures

- Total time and time per surgical step.
- Path length and smoothness of tool motion. (normalized by duration?)
- Workspace volume used by each tool. (note, will be relative to tool since the base frames are inaccurate in the rosbag)
- Number of grasps and regrasps.

## Analysis steps

can we make a gui/webapp to scroll through video and mark start and ends of suture/disections?
1. List all rosbags and videos, and match them to trials.
2. Line up video time with rosbag time.
3. Label surgical steps and sutures in the video.
4. Compute the measures for each trial.
5. Run statistics, with surgeon as a random effect.
6. Make figures.

## Discussion ideas

- Smaller tools suit infants, who have small mouths.
- Visual field is a useful new way to judge surgical tools.
- The paired video and rosbag data could be shared as a public dataset.
- Limits: pig vs human anatomy, small sample, learning curve on the new system.

## Open questions

- How many surgeons, trials, and pigs?
    1 surgeon, 8 pigs (4 for each tool size)
    The two May 3 mm trials were pilots, used to work out the process.
    So the comparison is 2 pigs (3 mm, June) vs 4 pigs (8 mm).
    Report the May trials separately, for feasibility only.
    Trial order (May, June, then Aug/Oct) favours 8 mm, since the surgeon had more practice by then.
- Which rosbag topics exist for each system?
- Is joint effort or force logged for both systems?
    measured_js using cisst crtk definition
- Is camera calibration available?
    no
- Were any trials stopped early or switched to another system?
- Which journal are we aiming for?
    journal of plastic and reconstructive surgery, ideas and innovation
