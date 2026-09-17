import { useMemo, useCallback } from 'react';
import { Sidebar } from 'primereact/sidebar';
import { Button } from 'primereact/button';
import { Chip } from 'primereact/chip';
import { Panel } from 'primereact/panel';
import { ButtonGroup } from 'primereact/buttongroup';
import React from 'react';
import VehicleGrid from './VehicleGrid.jsx';
import { toggleVehicleInSquad, recallControlGroup, squadMatchesGroup } from './squadUtils.js';
import { sortVehiclesForDisplay, vehicleStatus, vehicleStatusColor, vehicleStatusRailFill, isVehicleDisconnected } from './mapUtils.js';

const controlGroupDigits = ['1', '2', '3'];

export const VEHICLE_SIDEBAR_COLLAPSED_WIDTH = 56;
export const VEHICLE_SIDEBAR_EXPANDED_WIDTH = 360;

// Persistent, always-visible (modal={false}, no dismiss) app-wide sidebar
// showing the vehicle roster and control-group assign/recall -- rendered
// once in App.jsx (outside the per-tab conditional) so it, and its
// collapsed/expanded state, survive switching between Monitor/Control/Plan.
function VehicleSidebar({ vehicles, squadList, setSquadList, controlGroups, collapsed, setCollapsed }) {
  const sortedVehicles = useMemo(() => sortVehiclesForDisplay(vehicles, squadList), [vehicles, squadList]);
  const vehicleNames = useMemo(() => vehicles.map(v => v.name), [vehicles]);
  const connectedVehicleNames = useMemo(
    () => vehicles.filter(v => !isVehicleDisconnected(v)).map(v => v.name),
    [vehicles]
  );

  const onSelectAllSquad = useCallback(() => setSquadList([...connectedVehicleNames]), [connectedVehicleNames, setSquadList]);
  const onClearSquad = useCallback(() => setSquadList([]), [setSquadList]);
  const onRecallGroup = useCallback((digit) => setSquadList(recallControlGroup(controlGroups, digit)), [controlGroups, setSquadList]);
  const onToggleVehicle = useCallback((name) => setSquadList((prev) => toggleVehicleInSquad(prev, name)), [setSquadList]);

  const squadHeaderTemplate = (options) => (
    <div className={`${options.className} flex-column align-items-stretch`}>
      <div className="flex align-items-center justify-content-between mb-2">
        <div className="flex align-items-center gap-1">
          <Button size="small" rounded text label="" icon="pi pi-chevron-left" tooltip="Collapse" tooltipOptions={{ position: 'bottom' }} onClick={() => setCollapsed(true)} aria-label="Collapse squad list" />
          <span className="font-bold">Squad</span>
        </div>
        <Chip label={`${(squadList ?? []).length}/${vehicleNames.length} selected`} icon="pi pi-users" />
      </div>
      <div className="flex align-items-center justify-content-between flex-wrap gap-2">
        <div className="flex align-items-center gap-1">
          <Button size="small" rounded text label="" icon="pi pi-check-square" tooltip="Select All" tooltipOptions={{ position: 'bottom' }} onClick={onSelectAllSquad} aria-label="Select All" />
          <Button size="small" rounded text label="" icon="pi pi-times" tooltip="Clear" tooltipOptions={{ position: 'bottom' }} onClick={onClearSquad} aria-label="Clear" />
        </div>
        <ButtonGroup>
          {controlGroupDigits.map((digit) => {
            const hasVehicles = controlGroups[digit]?.length > 0;
            const isActive = hasVehicles && squadMatchesGroup(squadList, controlGroups, digit);
            return (
              <Button
                key={digit}
                size="small"
                outlined={!hasVehicles}
                severity={!hasVehicles ? 'secondary' : isActive ? 'success' : undefined}
                label={digit}
                tooltip={`Group ${digit}: ${(controlGroups[digit] ?? []).length} vehicles${isActive ? ' (currently selected)' : ''}`}
                tooltipOptions={{ position: 'bottom' }}
                onClick={() => onRecallGroup(digit)}
              />
            );
          })}
        </ButtonGroup>
      </div>
    </div>
  );

  return (
    <Sidebar
      visible
      modal={false}
      dismissable={false}
      showCloseIcon={false}
      closeOnEscape={false}
      onHide={() => {}}
      position="left"
      style={{ width: collapsed ? VEHICLE_SIDEBAR_COLLAPSED_WIDTH : VEHICLE_SIDEBAR_EXPANDED_WIDTH, transition: 'width 0.2s' }}
      pt={{ content: { style: { padding: 0 } } }}
    >
      <div className="h-full p-2">
        {collapsed ? (
          <div className="flex flex-column align-items-center gap-3 pt-2">
            <Button size="small" rounded text label="" icon="pi pi-chevron-right" tooltip="Expand" tooltipOptions={{ position: 'right' }} onClick={() => setCollapsed(false)} aria-label="Expand squad list" />
            {sortedVehicles.map((v) => {
              const disconnected = isVehicleDisconnected(v);
              const status = vehicleStatus(disconnected, !!(squadList && squadList.includes(v.name)));
              return (
                <span
                  key={v.name}
                  title={`${v.name} (${status})`}
                  onClick={disconnected ? undefined : () => onToggleVehicle(v.name)}
                  style={{
                    width: '12px', height: '12px', borderRadius: '50%',
                    cursor: disconnected ? 'not-allowed' : 'pointer',
                    backgroundColor: vehicleStatusRailFill(status),
                    border: `2px solid ${vehicleStatusColor(status)}`,
                    opacity: disconnected ? 0.6 : 1,
                  }}
                />
              );
            })}
          </div>
        ) : (
          <Panel headerTemplate={squadHeaderTemplate} className="h-full">
            <div className="grid m-0" style={{ maxHeight: 'calc(100vh - 220px)', overflowY: 'auto' }}>
              <VehicleGrid vehicles={sortedVehicles} selectable squadList={squadList} onToggle={onToggleVehicle} cardColumnClass="col-12 p-2" />
            </div>
          </Panel>
        )}
      </div>
    </Sidebar>
  );
}

export default React.memo(VehicleSidebar);
