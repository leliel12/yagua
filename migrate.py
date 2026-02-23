"""Migration: convert percentage values (0-100) to proportions (0-1).

Usage
-----
    python migrate.py <work_dir>
"""

import sys

from yagua.dal.models import EntropyMeasurementModel, TestModel
from yagua import project as yagua_project


def migrate_percentages_to_proportions(project):
    """Convert percentage values (0-100) to proportions (0-1) in the database.

    Only fields with values > 1 are converted, so the function is safe to
    run on databases that are already in the correct format.

    Parameters
    ----------
    project : Project
        Project instance whose store will be migrated.

    Returns
    -------
    dict
        Summary with keys:
        - 'project_fields': number of ProjectModel fields converted
        - 'test_fields': number of TestModel fields converted
        - 'entropy_fields': number of EntropyMeasurementModel fields converted
    """
    store = project.store
    project_fields = 0
    test_fields = 0
    entropy_fields = 0

    with store.transaction() as txn:
        proj = txn.project_model

        # --- ProjectModel ---
        proj_changed = False
        if proj.coverage is not None and proj.coverage > 1:
            proj.coverage /= 100.0
            project_fields += 1
            proj_changed = True
        if proj.msr is not None and proj.msr > 1:
            proj.msr /= 100.0
            project_fields += 1
            proj_changed = True
        if proj_changed:
            proj.save()

        # --- TestModel ---
        _proportion_fields = [
            "coverage_alone",
            "coverage_without",
            "msr_alone",
            "msr_without",
        ]
        for test in TestModel.select().where(TestModel.project == proj):
            test_changed = False
            for field in _proportion_fields:
                value = getattr(test, field)
                if value is not None and value > 1:
                    setattr(test, field, value / 100.0)
                    test_fields += 1
                    test_changed = True
            if test_changed:
                test.save()

    return {
        "project_fields": project_fields,
        "test_fields": test_fields,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <work_dir>")
        sys.exit(1)

    work_dir = sys.argv[1]
    project = yagua_project.from_work_dir(work_dir)
    result = migrate_percentages_to_proportions(project)

    print("Migration complete:")
    print(f"  project fields converted : {result['project_fields']}")
    print(f"  test fields converted    : {result['test_fields']}")
    print(f"  entropy fields converted : {result['entropy_fields']}")

