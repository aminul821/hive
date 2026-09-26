// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title HoneyLedger
 * @notice Tamper-evident anchor for honey supply-chain events.
 *
 * WHAT THIS STORES, AND WHY SO LITTLE
 *
 * Only a hash goes on-chain, never the underlying record. Batch weights,
 * beekeeper identities and harvest details live in Postgres; what is
 * anchored here is a SHA-256 fingerprint of the event.
 *
 * That split is deliberate:
 *
 *  - Privacy. A public chain is public forever. Putting a farmer's name
 *    or phone number on Sepolia would expose it permanently, with no way
 *    to erase it. A hash reveals nothing.
 *  - Cost. On-chain storage is expensive. A fixed-length hash costs the
 *    same whether the record behind it is one field or a thousand.
 *  - Sufficiency. The hash is all that is needed. To prove a record was
 *    not altered, recompute its hash and compare. If a single byte of the
 *    off-chain record changed, the hashes diverge and the tampering is
 *    provable by anyone, without trusting the operator.
 *
 * WHAT THIS DOES AND DOES NOT GUARANTEE
 *
 *  - It DOES prove that a given record existed, in exactly that form, at
 *    the block timestamp it was anchored.
 *  - It does NOT prove the record was TRUE when written. A beekeeper who
 *    lies about a harvest weight produces an honest hash of a false
 *    record. Catching that is the job of the off-chain integrity engine
 *    (integrity.py), which cross-checks declared weights against hive
 *    scale readings.
 *
 * Stating that boundary plainly matters more than the anchoring itself.
 * Blockchain makes records immutable, not honest.
 *
 * ---
 * Reconstructed from the deployed contract's ABI. The original source was
 * not kept, so this is functionally equivalent rather than byte-identical
 * — see contracts/README.md before attempting Etherscan verification.
 */
contract HoneyLedger {

    struct Record {
        string recordType;   // e.g. "BOTTLE_VERIFICATION", "HARVEST_VERIFICATION"
        string dataHash;     // SHA-256 of the canonical off-chain record
        uint256 timestamp;   // block time when anchored
        address addedBy;     // which account submitted it
    }

    /// @notice Every anchored record, in submission order.
    /// @dev Public, so `records(uint256)` is generated automatically.
    Record[] public records;

    event RecordAdded(
        uint256 indexed id,
        string recordType,
        string dataHash,
        uint256 timestamp,
        address addedBy
    );

    /**
     * @notice Anchor one event.
     * @param _recordType Category of event being recorded.
     * @param _dataHash   Hash of the off-chain record.
     *
     * Intentionally unrestricted: on a testnet demo, gating writes to a
     * single owner would stop a judge from anchoring their own record and
     * seeing it appear. A production deployment should add access
     * control, so that only registered processors can anchor — otherwise
     * anyone can pad the ledger with meaningless entries.
     */
    function addRecord(string memory _recordType, string memory _dataHash) public {
        records.push(Record({
            recordType: _recordType,
            dataHash: _dataHash,
            timestamp: block.timestamp,
            addedBy: msg.sender
        }));

        emit RecordAdded(
            records.length - 1,
            _recordType,
            _dataHash,
            block.timestamp,
            msg.sender
        );
    }

    /**
     * @notice Read one anchored record.
     * @param _id Index of the record.
     * @return recordType, dataHash, timestamp, addedBy
     */
    function getRecord(uint256 _id)
        public
        view
        returns (string memory, string memory, uint256, address)
    {
        require(_id < records.length, "HoneyLedger: record does not exist");
        Record storage r = records[_id];
        return (r.recordType, r.dataHash, r.timestamp, r.addedBy);
    }

    /// @notice How many records have been anchored.
    function getTotalRecords() public view returns (uint256) {
        return records.length;
    }
}
