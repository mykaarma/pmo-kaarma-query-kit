# Data catalog — where common business data lives

A starting map for turning plain-English requests into queries. Verified against production in Nov 2026; regenerate
`db_map/` (`python3 build_db_map.py`) for full column/index detail. Items marked **(confirm)** are best understanding,
not yet validated — check with a quick query before relying on them, and update this file when you learn more.

## Dealers (the backbone of almost every request) — `kaardbprod` → `KaarDBProd`
| Table | Use | Notes |
|---|---|---|
| `Dealer` | Master record: `ID`, `UUID`, `Name`, `NickName`, `LegalBusinessName`, `isValid`, `IsTestDealership`, `StartDate`, `EndDate`, `AddressID`, `InsertTS`, `UpdateTS` | Exclude test dealers by default (`IsTestDealership = 1`, 652 of ~4.5K). `isValid = 0` on ~1.7K dealers. `EndDate` is populated on almost every row, so it is **not** a churn date by itself **(confirm)** |
| `Address` | Dealer location: `City`, `StateCode`, `Zip` (join `Dealer.AddressID = Address.ID`) | Use `StateCode` for time zone |
| `DealerFranchisee` + `Brand` | **OEM / brand** of a dealer: `DealerFranchisee.DealerID`, `BrandID` → `Brand.BrandName`, `Brand.OEMID`; `DealerFranchisee.DealerCode` is JSON `{"DealerCode","Zone","District"}` (the OEM's own dealer code) | A dealer can have several franchises (rows). "Toyota dealers", "Stellantis dealers" etc. = filter on `Brand.BrandName` / `Brand.OEMID` |
| `DealerGroups`, `DealerGroupDealers` | Dealer groups | |
| `DealerFeature`, `DealerProductOption`, `DealerSubscription`, `Product` | Enabled features, product options/settings, subscriptions | Product catalog in `Product` (`ProductName`, `ProductType`, `BillingMethod`) |

### Onboarding / provisioning / churn — `KaarDBProd`
| Table | Use |
|---|---|
| `ProvisionStatus` | Pipeline stages: 1 Proposal Sent · 2 Contract Signed · 3 In Provisioning · 4 Ready for Training · 5 In Training · **6 Live** · **7 Canceled** |
| `ProvisionSubStatus` | Checklist items per stage, e.g. 13 Proposal Sent Date, 14 Contract Received, 20 DMS Credentials, 21 Twilio Credentials, 23 Training Date, 24/25 Training Start/End, **26 Go-Live Date**, **27 Canceled Date** (`ValueType` Date or Checkbox) |
| `DealerProvisionSubStatus` | A dealer's value per checklist item: `DealerID`, `SubStatusID`, `Value` (date string or True/False) → **go-live date = SubStatusID 26, churn/cancel date = SubStatusID 27** **(confirm)** |
| `ProvisionAuditLog` | History of checklist changes: `DealerID`, `SubStatusID`, `Date`, `DealerUserName` — use for "when did X happen" |
| `DealerGolive` | Empty — don't use |

## Phone numbers, toll-free and 10DLC — `communicationsaurora` → `CommunicationsDB` (source of truth)
`KaarDBProd` has older copies of these tables **without** the failure-reason columns — use CommunicationsDB.

| Table | Use | Notes |
|---|---|---|
| `VoiceCredentials` | Numbers provisioned to dealers: `BrokerNumber` (the phone number), `IsTollFree` (1 toll-free, 0 local/10DLC, NULL unknown), `DealerUUID`, `DepartmentUUID`, `UUID`, `IsHosted`, `BlacklistedOn`, `UseForOutgoingCommunication`, `InsertTS` | ~19K numbers. Join to dealer via `DealerUUID = KaarDBProd.Dealer.UUID` |
| `TollFreeDetails` | **Toll-free verification**: `VoiceCredentialsUUID` (= `VoiceCredentials.UUID`), `VerificationStatus`, `RegistrationFailureReason`, `RetryCount`, `InsertTS`, `UpdateTS` | Statuses seen: TWILIO_APPROVED, TWILIO_REJECTED, IN_REVIEW, PENDING_REVIEW, NOT_INITIATED, TWILIO_ERROR, MISSING_DETAILS_TO_PROCEED_WITH_REGISTRATION, DEALER_NOT_FOUND_FROM_KMANAGE |
| `DealerApplicationToPersonDetails` | **10DLC (A2P) registration** per dealer + department: `DealerUUID`, `DepartmentUUID`, `ProfileStatus`, `TrustProductStatus`, `BrandStatus`, `CampaignStatus`, `CampaignID`, `MessagingServiceSID`, `RegistrationFailureReason`, `InsertTS`, `UpdateTS` | Brand statuses: APPROVED / FAILED / PENDING; campaign: VERIFIED / FAILED / IN_PROGRESS / SUSPENDED; blank = not started. Fully approved ≈ BrandStatus APPROVED and CampaignStatus VERIFIED |
| `CloudPhoneNumber`, `CloudPhoneNumberType` | Cloud numbers by type (`CloudPhoneNumberTypeID`) | |

## Service declines — `KaarDBProd`
| Table | Use |
|---|---|
| `DeclinedOrder` | One row per repair order with declined work: `DealerID`, `DealerOrderID` (→ `DealerOrder.ID`), `InsertTS` |
| `DeclinedService` | Each declined item: `DeclinedOrderID` (→ `DeclinedOrder.ID`), `DeclinedRecommendationID`, `DeclinedOpcodeID`, `DeclineSource` (SERVICECART, DMS, DMSMPI) |
| `DeclinedRecommendation` | **What was declined**: `DeclineName` (e.g. Cabin Air Filter, Brake Fluid), `DeclineDescription`, `Opcode`, `Comments` |
| `DeclinedOpcode` | Dealer-specific decline opcode catalog (`DisplayName`, `InternalName`) — only ~22 rows |

"Decline reasons" usually means **what** service was declined (`DeclinedRecommendation.DeclineName`). There is no
structured "why the customer declined" field — `Comments` is free text **(confirm)**. Ask the requester which they mean.
Volumes are large (~7M rows): always filter by dealer and `InsertTS` range.

## Appointments — `scheduler` → `SchedulerDB` (source of truth; KaarDBProd copies are partial)
`ServiceAppointmentRequest` (SAR: `ID`, `SchedulerDealerID`, `CreatedTimeStamp`, `PreferredDate`, `Status`, `CreatedBy`,
`VehicleUUID`, `SchedulerCustomerID`), `SARMetaData` (JSON `MetaData`, booking source), `SARUpdateHistory` (status events),
`ServiceAppointmentRequestQuickOp` (booked operations, `RecallID`), `SchedulerDealer` (`DealerUUID` → `Dealer.UUID`).
Mongo `appointmentdb.DraftAppointment`: started-but-unbooked appointment drafts.

## Repair orders & vehicles — `KaarDBProd`
`DealerOrder` (`ID`, `UUID`, `DealerID`, `OrderNumber`, `OrderDate`, `CloseDate`, `OrderStatus`, `Amount` = customer-pay,
`PayTypes`, `VehicleID`, `ServiceAppointmentRequestID`); `Vehicle` (`ID`, `UUID`, `VIN`, `Model`, `Year`, `BrandID`) — one
VIN can have several `Vehicle` rows, so match vehicles on VIN.
