"""Forensics and data acquisition package for FBR34KER.

Provides chain-of-custody evidence collection, memory/storage/filesystem
acquisition, forensic imaging, iCloud/Keychain/Keybag extraction,
activation/baseband/FMI operations, and passcode management integrated
with the B34ST validation framework.
"""

from __future__ import annotations

from typing import Any

from host.forensics.chain_of_custody import (
    CustodyEntry,
    CustodyError,
    CustodyLog,
)
from host.forensics.acquisition import (
    AcquisitionEngine,
    AcquisitionError,
    AcquisitionResult,
    AcquisitionSession,
    AcquisitionTarget,
)
from host.forensics.memory import (
    MemoryAcquisitionError,
    MemoryAcquisitor,
    MemoryRegion,
)
from host.forensics.storage import (
    StorageAcquisitionError,
    StorageAcquisitor,
    StoragePartition,
)
from host.forensics.filesystem import (
    FileEntry,
    FileSystemAcquisitionError,
    FileSystemAcquisitor,
)
from host.forensics.network import (
    NetworkAcquisitionError,
    NetworkAcquisitor,
    NetworkInterfaceInfo,
)
from host.forensics.imaging import (
    ForensicImage,
    ImagingError,
    ImagingOptions,
)
from host.forensics.profiles import (
    AcquisitionProfile,
    ProfileError,
    builtin_profiles,
    load_profile,
)
from host.forensics.report import (
    AcquisitionReport,
    ReportError,
)
from host.forensics.secrets import (
    ICloudAcquisitor,
    KeybagAcquisitor,
    KeychainAcquisitor,
    SecretsAcquisitor,
    SecretsError,
    SepMailbox,
)
from host.forensics.activation import (
    ActivationBypass,
    ActivationError,
    ActivationOrchestrator,
    BasebandManager,
    FmiManager,
    MobileActivationManager,
)
from host.forensics.passcode import (
    PasscodeError,
    PasscodeManager,
)
from host.forensics.sep_key_fuzzer import (
    BOUNTY_SIGNIFICANCE,
    BASELINE_HARNESS_SWIFT,
    CANARY_LIBRARY,
    FUZZ_VARIATIONS,
    SEPKeyFuzzer,
    SEPKeyWrapper,
    FuzzTestResult,
    BountyReportSection,
    classify_result,
    generate_bounty_report,
    run_campaign,
)
from host.forensics.sep_research_pipeline import (
    SEPResearchPipeline,
    ArchitecturalMapper,
    RequestCorpus,
    DifferentialAnalyzer,
    StructuralFuzzer,
    StatefulFuzzer,
    ConcurrencyFuzzer,
    CrashTriager,
    run_pipeline,
)
from host.forensics.sep_deploy import (
    make_research_api,
    make_fuzzer_submit,
    deploy_swift_harness,
    list_backends,
    TRANSPORT_BACKENDS,
)

__all__ = [
    "AcquisitionEngine",
    "AcquisitionError",
    "AcquisitionProfile",
    "AcquisitionReport",
    "AcquisitionResult",
    "AcquisitionSession",
    "AcquisitionTarget",
    "ActivationBypass",
    "ActivationError",
    "ActivationOrchestrator",
    "BasebandManager",
    "CustodyEntry",
    "CustodyError",
    "CustodyLog",
    "FileEntry",
    "FileSystemAcquisitionError",
    "FileSystemAcquisitor",
    "FmiManager",
    "ForensicImage",
    "ImagingError",
    "ImagingOptions",
    "ICloudAcquisitor",
    "KeybagAcquisitor",
    "KeychainAcquisitor",
    "MemoryAcquisitionError",
    "MemoryAcquisitor",
    "MemoryRegion",
    "MobileActivationManager",
    "NetworkAcquisitionError",
    "NetworkAcquisitor",
    "NetworkInterfaceInfo",
    "PasscodeError",
    "PasscodeManager",
    "ProfileError",
    "ReportError",
    "SEPKeyFuzzer",
    "SEPKeyWrapper",
    "FuzzTestResult",
    "BountyReportSection",
    "classify_result",
    "generate_bounty_report",
    "run_campaign",
    "BOUNTY_SIGNIFICANCE",
    "CANARY_LIBRARY",
    "FUZZ_VARIATIONS",
    "BASELINE_HARNESS_SWIFT",
    "SEPResearchPipeline",
    "ArchitecturalMapper",
    "RequestCorpus",
    "DifferentialAnalyzer",
    "StructuralFuzzer",
    "StatefulFuzzer",
    "ConcurrencyFuzzer",
    "CrashTriager",
    "run_pipeline",
    "SecretsAcquisitor",
    "SecretsError",
    "SepMailbox",
    "StorageAcquisitionError",
    "StorageAcquisitor",
    "StoragePartition",
    "builtin_profiles",
    "load_profile",
    "make_research_api",
    "make_fuzzer_submit",
    "deploy_swift_harness",
    "list_backends",
    "TRANSPORT_BACKENDS",
]
