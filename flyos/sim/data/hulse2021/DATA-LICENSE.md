# Data licensing and attribution

The hemibrain-derived CSV data and their selected/reformatted JSON and CSV
derivatives in this directory are licensed under Creative Commons Attribution
4.0 International (CC BY 4.0), **not the repository-wide MIT license**.

- License: <https://creativecommons.org/licenses/by/4.0/>
- Legal text: <https://creativecommons.org/licenses/by/4.0/legalcode>
- Data provider's license statement:
  <https://www.janelia.org/project-team/flyem/hemibrain>

Attribution:

Hemibrain data: Scheffer et al. (2020), *A connectome and analysis of the adult
Drosophila central brain*, eLife 9:e57443.
<https://doi.org/10.7554/eLife.57443>

Central-complex analysis and saved tables: Hulse et al. (2021), *A connectome of
the Drosophila central complex reveals network motifs suitable for flexible
navigation and context-dependent action selection*, eLife 10:e66039.
<https://doi.org/10.7554/eLife.66039>

HHMI/Janelia FlyEM and the original research teams. No endorsement is implied.

Source: <https://github.com/jayaraman-lab/CX-connectome-analysis/tree/5c7a57256c15ea763e4cf0a7cf686ba0d3342d80/EBFigures/modularityAnalysis>

Changes made by FlyWatchOS: selected all positive ER4m/EPG cross-class EB rows
from the two saved exports; preserved original body IDs, instance names,
direction and ROIweight counts; sorted/reformatted records and indexed endpoints
for display. Original CSV bytes are preserved losslessly in timestamp-free gzip
files. No biological connection strengths were fitted, normalized or signed.

Keep attribution, source and license links, and the indication of changes with
redistributions. The indexed anatomy JSON embeds them so they travel with the
offline HTML bundle.

No standalone license for the upstream analysis repository's **code** was
identified at the pinned revision. No upstream MATLAB/R analysis code is copied
or required here, and no code license is inferred from the data license. The
new Python extractor and tests are independently written FlyWatchOS code under
this project's license.
