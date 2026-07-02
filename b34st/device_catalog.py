"""Reviewed launch metadata for device families supported by this project."""

# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

DEVICE_CATALOG = {
    "iPhone11,2": {"name": "iPhone XS", "launch_version": "12.0"},
    "iPhone11,4": {"name": "iPhone XS Max", "launch_version": "12.0"},
    "iPhone11,6": {"name": "iPhone XS Max (China)", "launch_version": "12.0"},
    "iPhone11,8": {"name": "iPhone XR", "launch_version": "12.0.1"},
    "iPhone12,1": {"name": "iPhone 11", "launch_version": "13.0"},
    "iPhone12,3": {"name": "iPhone 11 Pro", "launch_version": "13.0"},
    "iPhone12,5": {"name": "iPhone 11 Pro Max", "launch_version": "13.0"},
    "iPhone12,8": {"name": "iPhone SE (2nd generation)", "launch_version": "13.4"},
    "iPad8,1": {"name": "iPad Pro 11-inch (1st generation)", "launch_version": "12.1"},
    "iPad8,2": {"name": "iPad Pro 11-inch (1st generation)", "launch_version": "12.1"},
    "iPad8,3": {"name": "iPad Pro 11-inch (1st generation)", "launch_version": "12.1"},
    "iPad8,4": {"name": "iPad Pro 11-inch (1st generation)", "launch_version": "12.1"},
    "iPad8,5": {"name": "iPad Pro 12.9-inch (3rd generation)", "launch_version": "12.1"},
    "iPad8,6": {"name": "iPad Pro 12.9-inch (3rd generation)", "launch_version": "12.1"},
    "iPad8,7": {"name": "iPad Pro 12.9-inch (3rd generation)", "launch_version": "12.1"},
    "iPad8,8": {"name": "iPad Pro 12.9-inch (3rd generation)", "launch_version": "12.1"},
    "iPad8,9": {"name": "iPad Pro 11-inch (2nd generation)", "launch_version": "13.4"},
    "iPad8,10": {"name": "iPad Pro 11-inch (2nd generation)", "launch_version": "13.4"},
    "iPad8,11": {"name": "iPad Pro 12.9-inch (4th generation)", "launch_version": "13.4"},
    "iPad8,12": {"name": "iPad Pro 12.9-inch (4th generation)", "launch_version": "13.4"},
    "iPad11,1": {"name": "iPad mini (5th generation)", "launch_version": "12.2"},
    "iPad11,2": {"name": "iPad mini (5th generation)", "launch_version": "12.2"},
    "iPad11,3": {"name": "iPad Air (3rd generation)", "launch_version": "12.2"},
    "iPad11,4": {"name": "iPad Air (3rd generation)", "launch_version": "12.2"},
    "iPad11,6": {"name": "iPad (8th generation)", "launch_version": "14.0"},
    "iPad11,7": {"name": "iPad (8th generation)", "launch_version": "14.0"},
}


def device_metadata(product: str | None) -> dict[str, str] | None:
    if not product:
        return None
    value = DEVICE_CATALOG.get(product)
    return dict(value) if value else None
