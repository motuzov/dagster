import json

from dagster import AssetKey, StaticPartitionsDefinition, asset
from dagster._core.definitions.asset_graph import AssetGraph
from dagster._core.definitions.asset_reconciliation_sensor import (
    AssetReconciliationCursor,
)

partitions = StaticPartitionsDefinition(partition_keys=["a", "b", "c"])


@asset(partitions_def=partitions)
def my_asset(_):
    pass


def test_asset_reconciliation_cursor_evaluation_id_backcompat():
    backcompat_serialized = (
        """[20, ["a"], {"my_asset": "{\\"version\\": 1, \\"subset\\": [\\"a\\"]}"}]"""
    )

    assert (
        AssetReconciliationCursor.get_evaluation_id_from_serialized(backcompat_serialized) is None
    )

    asset_graph = AssetGraph.from_assets([my_asset])
    c = AssetReconciliationCursor.from_serialized(backcompat_serialized, asset_graph)

    assert c == AssetReconciliationCursor(
        20,
        {AssetKey("a")},
        {AssetKey("my_asset"): partitions.empty_subset().with_partition_keys(["a"])},
        0,
        {},
    )

    c2 = c.with_updates(
        21, [], {AssetKey("my_asset")}, {AssetKey("my_asset"): {"a"}}, 1, asset_graph, {}, 0
    )

    serdes_c2 = AssetReconciliationCursor.from_serialized(c2.serialize(), asset_graph)
    assert serdes_c2 == c2
    assert serdes_c2.evaluation_id == 1

    assert AssetReconciliationCursor.get_evaluation_id_from_serialized(c2.serialize()) == 1


def test_asset_reconciliation_cursor_auto_observe_backcompat():
    partitions_def = StaticPartitionsDefinition(["a", "b", "c"])

    @asset(partitions_def=partitions_def)
    def asset1():
        ...

    @asset
    def asset2():
        ...

    materialized_or_requested_root_partitions_by_asset_key = {
        asset1.key: partitions_def.subset_with_partition_keys(["a", "b"])
    }
    materialized_or_requested_root_asset_keys = {asset2.key}
    serialized = json.dumps(
        (
            25,
            [key.to_user_string() for key in materialized_or_requested_root_asset_keys],
            {
                key.to_user_string(): subset.serialize()
                for key, subset in materialized_or_requested_root_partitions_by_asset_key.items()
            },
        )
    )

    cursor = AssetReconciliationCursor.from_serialized(
        serialized, asset_graph=AssetGraph.from_assets([asset1, asset2])
    )
    assert cursor.latest_storage_id == 25
    assert (
        cursor.materialized_or_requested_root_asset_keys
        == materialized_or_requested_root_asset_keys
    )
    assert (
        cursor.materialized_or_requested_root_partitions_by_asset_key
        == materialized_or_requested_root_partitions_by_asset_key
    )
