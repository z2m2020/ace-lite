from ace_lite.cli_app import params_option_retrieval_groups
from ace_lite.cli_app.params_option_groups import (
    SHARED_CANDIDATE_OPTION_DESCRIPTORS,
    SHARED_CHUNK_OPTION_DESCRIPTORS,
    SHARED_EMBEDDING_OPTION_DESCRIPTORS,
    SHARED_INDEX_OPTION_DESCRIPTORS,
    SHARED_REPOMAP_OPTION_DESCRIPTORS,
)


def test_params_option_groups_facade_reexports_retrieval_group_descriptors() -> None:
    assert (
        SHARED_CHUNK_OPTION_DESCRIPTORS
        is params_option_retrieval_groups.SHARED_CHUNK_OPTION_DESCRIPTORS
    )
    assert (
        SHARED_CANDIDATE_OPTION_DESCRIPTORS
        is params_option_retrieval_groups.SHARED_CANDIDATE_OPTION_DESCRIPTORS
    )
    assert (
        SHARED_EMBEDDING_OPTION_DESCRIPTORS
        is params_option_retrieval_groups.SHARED_EMBEDDING_OPTION_DESCRIPTORS
    )
    assert (
        SHARED_INDEX_OPTION_DESCRIPTORS
        is params_option_retrieval_groups.SHARED_INDEX_OPTION_DESCRIPTORS
    )
    assert (
        SHARED_REPOMAP_OPTION_DESCRIPTORS
        is params_option_retrieval_groups.SHARED_REPOMAP_OPTION_DESCRIPTORS
    )
