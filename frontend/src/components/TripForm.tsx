import { useState, type FormEvent } from "react";

import { ApiError, planTrip } from "../services/api";
import type { TripInput, TripPlanResult } from "../types/trip";

interface TripFormProps {
  isLoading: boolean;
  onLoadingChange: (loading: boolean) => void;
  onError: (message: string) => void;
  onPlan: (result: TripPlanResult) => void;
}

interface FormValues {
  current_location: string;
  pickup_location: string;
  dropoff_location: string;
  cycle_used_hours: string;
}

const initialValues: FormValues = {
  current_location: "",
  pickup_location: "",
  dropoff_location: "",
  cycle_used_hours: "",
};

export function TripForm({ isLoading, onLoadingChange, onError, onPlan }: TripFormProps) {
  const [values, setValues] = useState<FormValues>(initialValues);
  const [validationError, setValidationError] = useState("");

  function updateValue(field: keyof FormValues, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
    if (validationError) setValidationError("");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isLoading) return;

    const locationFields: Array<[keyof FormValues, string]> = [
      ["current_location", "Current location"],
      ["pickup_location", "Pickup location"],
      ["dropoff_location", "Dropoff location"],
    ];
    const missingField = locationFields.find(([field]) => !values[field].trim());
    if (missingField) {
      const message = `${missingField[1]} is required.`;
      setValidationError(message);
      onError("");
      return;
    }

    const cycleUsedHours = Number(values.cycle_used_hours);
    if (!values.cycle_used_hours.trim() || !Number.isFinite(cycleUsedHours) || cycleUsedHours < 0 || cycleUsedHours > 70) {
      const message = "Current cycle used must be a number between 0 and 70 hours.";
      setValidationError(message);
      onError("");
      return;
    }

    const input: TripInput = {
      current_location: values.current_location.trim(),
      pickup_location: values.pickup_location.trim(),
      dropoff_location: values.dropoff_location.trim(),
      cycle_used_hours: cycleUsedHours,
    };

    setValidationError("");
    onError("");
    onLoadingChange(true);
    try {
      const result = await planTrip(input);
      onPlan(result);
    } catch (error) {
      onError(error instanceof ApiError ? error.message : "Unable to plan this trip right now.");
    } finally {
      onLoadingChange(false);
    }
  }

  return (
    <form className="trip-form" onSubmit={handleSubmit} noValidate aria-busy={isLoading}>
      <div className="form-heading">
        <div>
          <p className="eyebrow">Trip inputs</p>
          <h2>Plan a new journey</h2>
          <p className="form-intro">RoutePilot will map the drive and place each HOS stop in sequence.</p>
        </div>
        <span className="step-badge">PLAN</span>
      </div>

      <div className="form-fields">
        <label htmlFor="current-location">
          <span>Current location</span>
          <input
            id="current-location"
            value={values.current_location}
            onChange={(event) => updateValue("current_location", event.target.value)}
            placeholder="e.g. Chicago, IL"
            autoComplete="street-address"
            disabled={isLoading}
            aria-invalid={Boolean(validationError && !values.current_location.trim())}
          />
        </label>

        <label htmlFor="pickup-location">
          <span>Pickup location</span>
          <input
            id="pickup-location"
            value={values.pickup_location}
            onChange={(event) => updateValue("pickup_location", event.target.value)}
            placeholder="e.g. Dallas, TX"
            autoComplete="street-address"
            disabled={isLoading}
            aria-invalid={Boolean(validationError && !values.pickup_location.trim())}
          />
        </label>

        <label htmlFor="dropoff-location">
          <span>Dropoff location</span>
          <input
            id="dropoff-location"
            value={values.dropoff_location}
            onChange={(event) => updateValue("dropoff_location", event.target.value)}
            placeholder="e.g. Houston, TX"
            autoComplete="street-address"
            disabled={isLoading}
            aria-invalid={Boolean(validationError && !values.dropoff_location.trim())}
          />
        </label>

        <label htmlFor="cycle-used-hours">
          <span>Current cycle used</span>
          <span className="input-with-suffix">
            <input
              id="cycle-used-hours"
              type="number"
              min="0"
              max="70"
              step="any"
              inputMode="decimal"
              value={values.cycle_used_hours}
              onChange={(event) => updateValue("cycle_used_hours", event.target.value)}
              placeholder="24"
              disabled={isLoading}
              aria-describedby="cycle-help"
              aria-invalid={Boolean(validationError && values.cycle_used_hours !== "")}
            />
            <span aria-hidden="true">hours</span>
          </span>
          <small id="cycle-help">Rolling 70-hour / 8-day cycle already consumed before this plan starts.</small>
        </label>
      </div>

      {validationError && <p className="form-error" role="alert">{validationError}</p>}

      <button type="submit" className="primary-button" disabled={isLoading}>
        {isLoading ? "Building plan…" : <>Plan trip <span aria-hidden="true">→</span></>}
      </button>
      <p className="form-footnote">Uses live geocoding and route geometry. Results are planning guidance.</p>
    </form>
  );
}
